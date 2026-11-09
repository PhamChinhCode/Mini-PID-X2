#!/usr/bin/env python3
"""minipid - small CLI around kicad-cli + pcbnew for the MiniPID KiCad project.

Commands:
  info                 board size and object counts
  check [--json]       ERC + DRC (with schematic parity); exit 1 on DRC errors / unconnected
  refill               rebuild connectivity and refill all copper zones
  sync                 copy Value / Manufacturer Part / Supplier Part from schematic to footprints
  rules                print net classes and board rules from the project file
  fab [-o DIR]         Gerber + drill zip, JLCPCB BOM and CPL
  render [--side S]    3D PNG render (top|bottom|left|right|front|back)
"""
import argparse, csv, glob, json, os, re, subprocess, sys, tempfile, zipfile
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = os.path.basename(ROOT)
PCB = os.path.join(ROOT, NAME + '.kicad_pcb')
SCH = os.path.join(ROOT, NAME + '.kicad_sch')
PRO = os.path.join(ROOT, NAME + '.kicad_pro')
GERBER_LAYERS = 'F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts'


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode not in (0, 5):  # kicad-cli returns 5 when violations exist with --exit-code-violations
        sys.stderr.write(r.stdout + r.stderr)
    return r


def pcbnew():
    import pcbnew as p
    return p


def editor_open():
    return [f for f in glob.glob(os.path.join(ROOT, '~*.lck')) if f.endswith(('.kicad_pcb.lck', '.kicad_sch.lck'))]


def require_closed():
    locks = editor_open()
    if locks:
        sys.exit('KiCad is editing this project (%s). Save and close the editor first.' % ', '.join(os.path.basename(l) for l in locks))


def sch_symbols():
    """Return {ref: {field: value}} for placed symbols in the schematic."""
    s = open(SCH, encoding='utf-8').read()
    starts = [m.start() for m in re.finditer(r'\n\t\(symbol\n\t\t\(lib_id', s)]
    out = {}
    for k, i in enumerate(starts):
        blk = s[i:starts[k + 1] if k + 1 < len(starts) else len(s)]
        props = dict(re.findall(r'\(property "([^"]*)" "((?:[^"\\]|\\.)*)"', blk))
        ref = props.get('Reference', '')
        if ref and not ref.startswith('#') and ref != '?':
            out[ref] = props
    return out


def cmd_info(a):
    p = pcbnew()
    b = p.LoadBoard(PCB)
    bb = b.GetBoardEdgesBoundingBox()
    tracks = [t for t in b.GetTracks()]
    vias = [t for t in tracks if t.GetClass() == 'PCB_VIA']
    print('Board      : %.2f x %.2f mm, %d copper layers' % (p.ToMM(bb.GetWidth()), p.ToMM(bb.GetHeight()), b.GetCopperLayerCount()))
    print('Footprints : %d' % len(b.GetFootprints()))
    print('Nets       : %d' % (b.GetNetCount() - 1))
    print('Tracks     : %d   Vias: %d   Zones: %d' % (len(tracks) - len(vias), len(vias), b.GetAreaCount()))
    for z in b.Zones():
        layers = '+'.join(n for n, l in (('F.Cu', p.F_Cu), ('B.Cu', p.B_Cu)) if z.IsOnLayer(l))
        print('  zone %-8s %-5s priority %d' % (z.GetNetname(), layers, z.GetAssignedPriority()))


def cmd_check(a):
    tmp = tempfile.mkdtemp(prefix='minipid-check-')
    erc, drc = os.path.join(tmp, 'erc.json'), os.path.join(tmp, 'drc.json')
    run(['kicad-cli', 'sch', 'erc', '--format', 'json', '-o', erc, SCH])
    run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--schematic-parity', '-o', drc, PCB])
    e = json.load(open(erc)); d = json.load(open(drc))
    ev = [x for s in e['sheets'] for x in s['violations']]
    res = {'erc': Counter((x['severity'], x['type']) for x in ev),
           'drc': Counter((x['severity'], x['type']) for x in d.get('violations', [])),
           'unconnected': len(d.get('unconnected_items', [])),
           'parity': Counter((x['severity'], x['type']) for x in d.get('schematic_parity', []))}
    if a.json:
        print(json.dumps({k: (v if isinstance(v, int) else {'%s:%s' % kk: n for kk, n in v.items()}) for k, v in res.items()}, indent=2))
    else:
        for k in ('drc', 'parity', 'erc'):
            tot = sum(res[k].values())
            errs = sum(n for (sev, _), n in res[k].items() if sev == 'error')
            print('%-7s %4d issues (%d errors)' % (k.upper(), tot, errs))
            for (sev, typ), n in res[k].most_common(8):
                print('          %-7s %-32s %d' % (sev, typ, n))
        print('UNCONNECTED %d' % res['unconnected'])
        print('reports: %s' % tmp)
    drc_err = sum(n for (sev, _), n in res['drc'].items() if sev == 'error')
    sys.exit(1 if (drc_err or res['unconnected']) else 0)


def cmd_refill(a):
    require_closed()
    p = pcbnew()
    b = p.LoadBoard(PCB)
    b.BuildConnectivity()
    p.ZONE_FILLER(b).Fill(b.Zones())
    b.BuildConnectivity()
    p.SaveBoard(PCB, b)
    print('refilled %d zones' % b.GetAreaCount())


def cmd_sync(a):
    require_closed()
    p = pcbnew()
    syms = sch_symbols()
    b = p.LoadBoard(PCB)
    changed = 0
    for f in b.GetFootprints():
        s = syms.get(f.GetReference())
        if not s:
            continue
        if s.get('Value') and f.GetValue() != s['Value']:
            f.SetValue(s['Value']); changed += 1
        for name, val in s.items():
            if name in ('Reference', 'Value', 'Footprint') or name.startswith('ki_'):
                continue
            if not val:
                continue
            fld = f.GetField(name) if hasattr(f, 'GetField') else None
            if fld is None and hasattr(f, 'GetFieldByName'):
                fld = f.GetFieldByName(name)
            if fld is None:
                fld = p.PCB_FIELD(f, p.FIELD_T_USER, name)
                fld.SetVisible(False); fld.SetLayer(p.F_Fab); f.Add(fld)
            if fld.GetText() != val:
                fld.SetText(val); changed += 1
    p.SaveBoard(PCB, b)
    print('updated %d footprint fields from schematic' % changed)


def cmd_rules(a):
    pro = json.load(open(PRO))
    r = pro['board']['design_settings']['rules']
    print('Board rules: clearance %.3f  track %.3f  via %.2f/%.2f  edge %.2f mm' % (
        r['min_clearance'], r['min_track_width'], r['min_via_diameter'], r['min_through_hole_diameter'], r['min_copper_edge_clearance']))
    pats = defaultdict(list)
    for x in pro['net_settings'].get('netclass_patterns', []):
        pats[x['netclass']].append(x['pattern'])
    print('%-8s %6s %6s %10s  nets' % ('class', 'track', 'clear', 'via'))
    for c in pro['net_settings']['classes']:
        print('%-8s %6.3f %6.3f %5.2f/%.2f  %s' % (c['name'], c['track_width'], c['clearance'], c['via_diameter'], c['via_drill'],
                                                 ', '.join(pats.get(c['name'], [])) or '(all others)'))


def cmd_fab(a):
    out = os.path.abspath(a.output or os.path.join(ROOT, 'fab'))
    gdir = os.path.join(out, 'gerber')
    os.makedirs(gdir, exist_ok=True)
    for old in glob.glob(os.path.join(gdir, '*')): os.remove(old)
    run(['kicad-cli', 'pcb', 'export', 'gerbers', '--check-zones', '--use-drill-file-origin', '-l', GERBER_LAYERS, '-o', gdir + '/', PCB])
    run(['kicad-cli', 'pcb', 'export', 'drill', '--format', 'excellon', '--excellon-units', 'mm', '--drill-origin', 'plot', '-o', gdir + '/', PCB])
    zpath = os.path.join(out, NAME + '_gerber.zip')
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(gdir)):
            z.write(os.path.join(gdir, f), f)
    # BOM (JLCPCB: Comment, Designator, Footprint, LCSC Part #)
    syms = sch_symbols()
    groups = defaultdict(list)
    for ref, s in syms.items():
        if s.get('Add into BOM', 'yes').lower() == 'no':
            continue
        fp = s.get('Footprint', '').split(':')[-1]
        groups[(s.get('Value', ''), fp, s.get('LCSC') or s.get('Supplier Part', ''))].append(ref)
    nat = lambda r: (re.sub(r'\d+', '', r), int(re.sub(r'\D', '', r) or 0))
    bom = os.path.join(out, NAME + '_BOM_JLC.csv')
    with open(bom, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh); w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        for (val, fp, lcsc), refs in sorted(groups.items(), key=lambda kv: nat(sorted(kv[1], key=nat)[0])):
            w.writerow([val, ','.join(sorted(refs, key=nat)), fp, lcsc])
    # CPL (JLCPCB: Designator, Mid X, Mid Y, Layer, Rotation)
    pos = os.path.join(out, 'pos_raw.csv')
    run(['kicad-cli', 'pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'both', '--exclude-dnp', '--use-drill-file-origin', '-o', pos, PCB])
    cpl = os.path.join(out, NAME + '_CPL_JLC.csv')
    n = 0
    with open(pos, encoding='utf-8') as fi, open(cpl, 'w', newline='', encoding='utf-8') as fo:
        w = csv.writer(fo); w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for r in csv.DictReader(fi):
            if r['Ref'] not in syms:
                continue
            w.writerow([r['Ref'], r['PosX'] + 'mm', r['PosY'] + 'mm', 'Top' if r['Side'] == 'top' else 'Bottom', r['Rot']]); n += 1
    os.remove(pos)
    print('gerber zip : %s' % zpath)
    print('BOM        : %s (%d lines)' % (bom, len(groups)))
    print('CPL        : %s (%d parts)' % (cpl, n))


def cmd_render(a):
    out = os.path.abspath(a.output or os.path.join(ROOT, 'render_%s.png' % a.side))
    run(['kicad-cli', 'pcb', 'render', '--side', a.side, '--quality', 'high', '-w', '1600', '-h', '1100', '-o', out, PCB])
    print(out)


def main():
    ap = argparse.ArgumentParser(prog='minipid', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    sp.add_parser('info').set_defaults(fn=cmd_info)
    c = sp.add_parser('check'); c.add_argument('--json', action='store_true'); c.set_defaults(fn=cmd_check)
    sp.add_parser('refill').set_defaults(fn=cmd_refill)
    sp.add_parser('sync').set_defaults(fn=cmd_sync)
    sp.add_parser('rules').set_defaults(fn=cmd_rules)
    f = sp.add_parser('fab'); f.add_argument('-o', '--output'); f.set_defaults(fn=cmd_fab)
    r = sp.add_parser('render'); r.add_argument('--side', default='top', choices=['top', 'bottom', 'left', 'right', 'front', 'back'])
    r.add_argument('-o', '--output'); r.set_defaults(fn=cmd_render)
    a = ap.parse_args(); a.fn(a)


if __name__ == '__main__':
    main()
