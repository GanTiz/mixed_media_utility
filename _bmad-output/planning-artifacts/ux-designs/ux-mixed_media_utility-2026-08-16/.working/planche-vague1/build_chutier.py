# -*- coding: utf-8 -*-
"""Chutier v2, revision du 21 aout : applique les six retours d'Egan."""
import sys, pathlib
S = pathlib.Path('/tmp/claude-0/-home-user-mixed-media-utility/c54b30dd-4fc6-5b3c-9cf8-4e164b2f3aef/scratchpad')
sys.path.insert(0, str(S))
from picto import PICTOS

M = pathlib.Path('/home/user/mixed_media_utility/_bmad-output/planning-artifacts/ux-designs/ux-mixed_media_utility-2026-08-16/mockups')

def row(kind, nom, meta='', *, niveau=0, ouvert=None, puce='', sel=False, kin=False,
        sig='', enfants=None):
    """Une ligne d'arbre. `ouvert` : True (deplie, signe -), False (replie, signe +),
    None (feuille, pas de signe -- c'est ce qui distingue un parent d'un enfant final)."""
    exp = '<span class="exp none"></span>'
    if ouvert is True:
        exp = '<span class="exp">&minus;</span>'
    elif ouvert is False:
        exp = '<span class="exp">+</span>'
    cls = 'row' + (' sel' if sel else '') + (' kin' if kin else '')
    p = f'<span class="puce {puce}"></span>' if puce is not None else ''
    m = f'<span class="meta">{meta}</span>' if meta else ''
    s = f'<span class="sig {sig[0]}" title="{sig[1]}">{sig[2]}</span>' if sig else ''
    return (f'<div class="node"><div class="{cls}">{exp}{p}{PICTOS[kind]}'
            f'<span class="nm">{nom}</span>{m}{s}</div>'
            + (f'<div class="kids">{enfants}</div>' if enfants else '')
            + '</div>')

TOKENS = (S / 'tokens.css').read_text(encoding='utf-8')

CSS = """
/* --- l'arbre, revision du 21 aout ----------------------------------------
   Ce qui a change, retour par retour :
     * pictogrammes au lieu de lettres dans un cartouche ;
     * le cartouche et le trait d'accent a gauche disparaissent : il ne reste
       que la puce, le pictogramme et le nom ;
     * la fleche devient un + / - fin, et son ABSENCE dit qu'un objet n'a pas
       d'enfant -- c'est ce qui distingue un parent d'un enfant final ;
     * les traits d'arbre s'arretent au dernier objet d'un niveau ;
     * la selection se lit sur la puce : pleine quand tous les enfants sont
       pris, un point quand la selection est ponctuelle.
   -------------------------------------------------------------------------- */
.bin{position:relative; width:330px; flex:0 0 330px; background:var(--surface-panel); border-right:1px solid var(--border); display:flex; flex-direction:column}
.bin-head{padding:var(--panel-pad); border-bottom:1px solid var(--border); display:flex; align-items:center; justify-content:space-between; gap:var(--sp4)}
.bin-scope{font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--text-secondary)}
.meta{flex:0 0 auto; white-space:nowrap; font-family:var(--f-data); font-size:11px; color:var(--text-disabled); font-variant-numeric:tabular-nums}
.mono{font-family:var(--f-data); font-size:12px; font-variant-numeric:tabular-nums}

/* les filtres se deploient, ils ne tiennent pas la place en permanence */
.filtres{display:flex; align-items:center; gap:var(--sp4); padding:var(--sp3) var(--panel-pad); border-bottom:1px solid var(--border)}
.filtres .tog{display:inline-flex; align-items:center; gap:var(--sp3); font-size:11px; color:var(--text-secondary); border:1px solid var(--border); border-radius:var(--r-sm); padding:1px var(--sp4)}
.filtres .tog .car{color:var(--text-disabled); font-size:9px}
.filtres .cur{font-family:var(--f-data); font-size:10.5px; color:var(--text-disabled)}
.filtres-open{display:flex; gap:var(--sp2); flex-wrap:wrap; padding:var(--sp3) var(--panel-pad) var(--sp4); border-bottom:1px solid var(--border)}
.filtre{font-size:10.5px; color:var(--text-disabled); border:1px solid var(--border); border-radius:var(--r-full); padding:1px var(--sp4)}
.filtre.on{color:var(--text-primary); border-color:var(--border-strong); background:var(--surface-raised)}

.tree{flex:1 1 auto; padding:var(--sp4) var(--sp4) var(--sp4) var(--sp3); overflow:hidden}
.node{position:relative}
.kids{margin-left:8px; padding-left:12px}
.kids > .node::before{content:""; position:absolute; left:-12px; top:0; bottom:0; width:1px; background:var(--border)}
.kids > .node:last-child::before{height:14px; bottom:auto}
.kids > .node > .row::before{content:""; position:absolute; left:-12px; top:14px; width:9px; height:1px; background:var(--border)}
.row{position:relative; min-height:var(--row-height); display:flex; align-items:center; gap:var(--sp3); padding:0 var(--sp4) 0 0; border-radius:var(--r-md); color:var(--text-primary)}
.row.sel{background:var(--surface-hover)}
.exp{width:11px; flex:0 0 11px; text-align:center; font-family:var(--f-data); font-size:11px; color:var(--text-disabled); line-height:1}
.exp.none{visibility:hidden}
.pi{flex:0 0 15px; color:var(--text-secondary)}
.row.sel .pi{color:var(--text-primary)}
.nm{flex:1 1 auto; overflow:hidden; text-overflow:ellipsis; white-space:nowrap}

/* puce de selection : vide, pleine (tous les enfants), point (selection ponctuelle) */
.puce{position:relative; width:13px; height:13px; flex:0 0 13px; border:1px solid var(--border-strong); border-radius:var(--r-sm); background:var(--surface-raised)}
.puce.all{background:var(--accent); border-color:var(--accent)}
.puce.all::after{content:""; position:absolute; left:4px; top:1px; width:3px; height:7px; border:solid var(--accent-on); border-width:0 2px 2px 0; transform:rotate(42deg)}
.puce.some::after{content:""; position:absolute; left:3px; top:3px; width:5px; height:5px; border-radius:1px; background:var(--accent)}

/* signes d'etat : lisibles, et porteurs d'une info-bulle */
.sig{flex:0 0 auto; font-family:var(--f-data); font-size:14px; line-height:1; cursor:default}
.sig.delie{color:var(--state-absent)}
.sig.libre{color:var(--state-substitute)}
.sig.incomplet{color:var(--state-substitute); font-size:15px}
.bulle{position:absolute; z-index:5; max-width:230px; padding:var(--sp4) var(--sp5); background:var(--surface-raised);
  border:1px solid var(--border-strong); border-radius:var(--r-md); box-shadow:0 6px 20px rgba(0,0,0,.5);
  font-size:11.5px; line-height:1.45; color:var(--text-primary)}
.bulle b{color:var(--state-substitute); font-weight:600}

/* file d'attente de lecture, en haut */
.queue{margin:var(--sp4) var(--sp4) 0; padding:var(--panel-pad); background:var(--surface-sunken); border:1px dashed var(--border); border-radius:var(--r-md)}
.queue-title{font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--text-secondary);display:flex;justify-content:space-between;margin-bottom:var(--sp4)}
.chk{display:flex;align-items:center;gap:var(--sp4);min-height:var(--hit-min);color:var(--text-secondary)}

/* fil d'Ariane */
.fil{display:flex;align-items:center;gap:var(--sp3);padding:var(--sp4) var(--panel-pad);border-bottom:1px solid var(--border);
  font-family:var(--f-data);font-size:11px;color:var(--text-disabled);white-space:nowrap;overflow:hidden}
.fil .path{flex:1 1 auto;overflow:hidden;text-overflow:ellipsis;direction:rtl;text-align:left}
.fil .path span{direction:ltr;unicode-bidi:embed}
.fil b{color:var(--text-primary);font-weight:500}
.fil .up{border:1px solid var(--border);border-radius:var(--r-sm);padding:0 var(--sp3);color:var(--text-secondary)}

.work{flex:1 1 auto; display:flex; flex-direction:column; background:var(--surface-canvas); position:relative}
.notes{flex:1 1 auto; padding:var(--sp6) var(--sp7)}
.notes.hors{background:transparent; padding:var(--sp6) 0 0}
.note{display:flex; gap:var(--sp5); padding:var(--sp4) 0; border-bottom:1px solid var(--border)}
.note:last-child{border-bottom:0}
.num{flex:0 0 20px;height:20px;border-radius:var(--r-full);background:var(--surface-raised);border:1px solid var(--border-strong);color:var(--text-secondary);font-family:var(--f-data);font-size:11px;display:flex;align-items:center;justify-content:center}
.note b{color:var(--text-primary);font-weight:600} .note p{margin:0;color:var(--text-secondary)}
.actionbar{display:flex; align-items:center; gap:var(--sp5); padding:var(--sp5) var(--sp7); border-top:1px solid var(--border); background:var(--surface-panel)}
.actionbar .say{flex:1 1 auto; color:var(--text-secondary); font-size:12px}
.btn{white-space:nowrap; background:var(--accent); color:var(--accent-on); border:0; border-radius:var(--r-md); padding:var(--sp4) var(--sp6); font-family:var(--f-ui); font-size:13px; font-weight:600}
.btn.ghost{background:transparent; color:var(--text-secondary); border:1px solid var(--border-strong)}

/* fenetre flottante a l'import, plutot qu'un bandeau */
.scrim{position:absolute; inset:0; background:rgba(0,0,0,.5); display:flex; align-items:center; justify-content:center}
.fen{width:380px; background:var(--surface-panel); border:1px solid var(--border-strong); border-radius:var(--r-lg); box-shadow:0 18px 50px rgba(0,0,0,.6); padding:var(--sp6)}
.fen h4{margin:0 0 var(--sp4); font-size:14px; font-weight:600}
.fen p{margin:0 0 var(--sp5); color:var(--text-secondary); font-size:12.5px}
.fen .file{font-family:var(--f-data); font-size:11px; color:var(--state-substitute); display:block; margin-bottom:var(--sp3)}
.fen .row2{display:flex; gap:var(--sp4); justify-content:flex-end}

/* --- panneau lateral : l'arborescence y vit, le chutier montre le contenu ---
   Fil 4450750c : « l'arborescence a sa place sur un panneau lateral
   retractable. Et le chutier est par defaut le contenu de l'objet parent. »
   Modele de l'explorateur de fichiers et de Resolve. */
.nav{position:relative; width:196px; flex:0 0 196px; background:var(--surface-sunken);
  border-right:1px solid var(--border); display:flex; flex-direction:column}
.nav.pli{width:42px; flex:0 0 42px}
.nav-head{display:flex; align-items:center; justify-content:space-between; gap:var(--sp3);
  padding:var(--panel-pad); border-bottom:1px solid var(--border)}
.nav-head .t{font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--text-disabled)}
.nav-head .pl{border:1px solid var(--border); border-radius:var(--r-sm); padding:0 var(--sp3);
  font-family:var(--f-data); font-size:10px; color:var(--text-secondary)}
.nav .tree{padding:var(--sp4) var(--sp4) var(--sp4) var(--sp3)}
.nav .row{min-height:26px}
.nav .row.here{background:var(--surface-hover)}
.nav .row.here .nm{color:var(--text-primary)}
.nav .nm{color:var(--text-secondary); font-size:12.5px}
.nav.pli .nm, .nav.pli .exp, .nav.pli .meta{display:none}
.nav.pli .row{justify-content:center; padding:0}
/* la poignee de separation : la largeur des panneaux se regle */
.poignee{position:absolute; right:-3px; top:0; bottom:0; width:5px; cursor:col-resize; z-index:2}
.poignee::after{content:""; position:absolute; left:2px; top:50%; width:1px; height:26px; margin-top:-13px; background:var(--border-strong)}

.bin-head .plein{border:1px solid var(--border); border-radius:var(--r-sm); padding:0 var(--sp4);
  font-family:var(--f-data); font-size:10px; color:var(--text-secondary)}
.portee{font-family:var(--f-data); font-size:10.5px; color:var(--text-disabled); padding:0 var(--panel-pad) var(--sp4)}
.portee b{color:var(--text-secondary); font-weight:500}
/* saisie manuelle du parent, pour un media qui attend */
.rattacher{display:flex; align-items:center; gap:var(--sp4); margin-top:var(--sp4); padding-top:var(--sp4); border-top:1px dashed var(--border)}
.rattacher .in{flex:1 1 auto; height:24px; border:1px solid var(--border-strong); border-radius:var(--r-sm);
  background:var(--surface-panel); display:flex; align-items:center; padding:0 var(--sp4);
  font-family:var(--f-data); font-size:11px; color:var(--text-disabled)}
.rattacher .go{border:1px solid var(--border-strong); border-radius:var(--r-sm); padding:1px var(--sp4); font-size:11px; color:var(--text-secondary); white-space:nowrap}

.sheet{max-width:1180px;margin:0 auto;padding:var(--sp8) var(--sp6) 64px}
h1{font-size:28px;font-weight:600;line-height:1.2;margin:0 0 var(--sp3)}
.sub{color:var(--text-secondary);margin:0 0 var(--sp8);max-width:74ch}
h2{font-size:15px;font-weight:600;line-height:1.3;margin:var(--sp8) 0 var(--sp5)}
.caption{color:var(--text-secondary);margin:var(--sp5) 0 0;font-size:12px;max-width:80ch}
.legend{display:flex;flex-wrap:wrap;gap:var(--sp6);margin:var(--sp5) 0 0;color:var(--text-secondary);font-size:12px}
.legend span{display:inline-flex;align-items:center;gap:var(--sp3)}
code{font-family:var(--f-data);font-size:11px;color:var(--text-secondary)}
b.k{color:var(--text-primary);font-weight:600}
"""

# ------------------------------------------------------------- navigateur
def nav(sel):
    """L'arborescence, reduite aux noms : elle sert a se placer, pas a travailler."""
    def n(kind, nom, *, ouvert=None, ici=False, enfants=''):
        exp = '<span class="exp none"></span>'
        if ouvert is True: exp = '<span class="exp">&minus;</span>'
        elif ouvert is False: exp = '<span class="exp">+</span>'
        cls = 'row here' if ici else 'row'
        return (f'<div class="node"><div class="{cls}">{exp}{PICTOS[kind]}<span class="nm">{nom}</span></div>'
                + (f'<div class="kids">{enfants}</div>' if enfants else '') + '</div>')
    return n('dossier', 'sequence 3', ouvert=True, ici=(sel == 'seq'), enfants=(
        n('rush', 'TEST_FILE_12p5.mov', ouvert=True, enfants=(
            n('extr', 'Extraction 12,5 fps', ouvert=False, ici=(sel == 'lot'))
            + n('extr', 'Extraction 25 fps', ouvert=False)
            + n('extr', 'Extraction 50 fps')
        ))
        + n('rush', 'plan-large-25.mov', ouvert=False)
    ))

# ------------------------------------- etat A : la sequence est selectionnee
# construit de bas en haut : plus lisible qu'une imbrication de parentheses
_encode = row('encode', 'rush-12p5-reconstruit.mov', '00:32')
_lotr = row('lotr', 'Lot reconstruit', '9 f.', ouvert=True, enfants=_encode)
_scan = row('scan', 'scan-planches-01.tif', '600 ppp', ouvert=True, enfants=_lotr)
_planche = row('planche', 'Planche A4-6f', '9 p.', ouvert=True, enfants=_scan)
_extractions = (
    row('extr', 'Extraction 12,5 fps', '9 f.', ouvert=True, puce='all', enfants=_planche)
    + row('extr', 'Extraction 25 fps', '18 f.', ouvert=False, puce='all')
    + row('extr', 'Extraction 50 fps', '36 f.', puce='all')
)
chutier_a = (
    row('rush', 'TEST_FILE_12p5.mov', '1080p', ouvert=True, puce='all', sel=True, enfants=_extractions)
    + row('rush', 'plan-large-25.mov', ouvert=False, puce='',
          sig=('delie', "Le fichier a disparu du disque : le retrouver pour relier.", '&#8856;'))
)

etat_a = f'''
  <h2>Etat A &mdash; le panneau lateral designe, le chutier montre</h2>
  <div class="app">
    <div class="app-header"><span class="app-title">Pdf</span></div>
    <div class="app-body">
      <div class="nav">
        <div class="nav-head"><span class="t">Arborescence</span><span class="pl">&#8676;</span></div>
        <div class="tree">{nav('seq')}</div>
        <div class="poignee"></div>
      </div>
      <div class="bin">
        <div class="bin-head"><span class="bin-scope">Chutier</span><span class="plein">plein ecran</span></div>
        <div class="portee">Contenu de <b>sequence 3</b> &middot; 2 rushes</div>
        <div class="filtres"><span class="tog"><span class="car">&#9656;</span>Filtres</span><span class="cur">tout</span></div>
        <div class="queue">
          <div class="queue-title"><span>En attente de lecture</span><span class="meta">2</span></div>
          <div class="chk"><span class="puce"></span><span class="mono">scan-planches-03.tif</span></div>
          <div class="chk"><span class="puce"></span><span class="mono">scan-planches-04.tif</span></div>
        </div>
        <div class="tree">{chutier_a}</div>
      </div>
      <div class="work">
        <div class="notes">
          <div class="note"><span class="num">1</span><p><b>Deux panneaux, deux roles.</b> A gauche
            l'arborescence : elle sert a <i>se placer</i>. Au centre le chutier : il montre le
            <i>contenu</i> de l'objet designe. Ici <i>sequence 3</i> est selectionnee, donc le
            chutier porte tous ses rushes et leurs enfants.</p></div>
          <div class="note"><span class="num">2</span><p><b>La question « qu'est-ce qui fait qu'on
            entre dans une branche » disparait.</b> Il n'y a plus de mode a activer : on designe a
            gauche, on lit a droite. Le fil d'Ariane devient inutile &mdash; le panneau lateral
            <i>est</i> le fil, et il est toujours la.</p></div>
          <div class="note"><span class="num">3</span><p><b>Les largeurs se reglent</b> par la
            poignee, et le panneau lateral se retracte. Sous une certaine largeur de fenetre il se
            retracte seul &mdash; le chutier passe avant lui &mdash; mais il <b>se rappelle d'un
            geste</b> : le rail des pictogrammes reste touchable et rouvre l'arborescence
            <i>par-dessus</i> le chutier, le temps de se placer. On a bien l'un ou l'autre, mais
            jamais rien.</p></div>
          <div class="note"><span class="num">4</span><p><b>Le reste tient.</b> La puce dit la
            selection &mdash; pleine quand tous les enfants sont pris, un point quand elle est
            ponctuelle. Le signe + dit qu'il y a des enfants, son absence dit qu'il n'y en a pas.
            Les traits s'arretent au dernier objet d'un niveau.</p></div>
        </div>
        <div class="actionbar">
          <span class="say">3 extractions selectionnees &mdash; rush <span class="mono">TEST_FILE_12p5.mov</span></span>
          <button class="btn ghost" type="button">Vider la selection</button>
          <button class="btn" type="button">Generer 3 planches</button>
        </div>
      </div>
    </div>
  </div>
  <p class="caption">Modele de l'explorateur de fichiers et de Resolve : la selection du panneau
  lateral fixe la portee du chutier, et le chutier reste un arbre &mdash; on continue d'y deplier
  ce qu'on veut.</p>
'''

# ------------------------------------------ etat B : un lot est selectionne
_lotr_b = row('lotr', 'Lot reconstruit', '7 / 9 f.', puce='', sel=True,
              sig=('incomplet', 'Deux pages manquent : 8 et 9. A scanner.', '&#9888;'))
_scan_b = row('scan', 'scan-planches-01.tif', '600 ppp', ouvert=True, puce='', enfants=_lotr_b)
chutier_b = row('planche', 'Planche A4-6f', '9 p.', ouvert=True, puce='',
                enfants=_scan_b + row('scan', 'scan-planches-02.tif', '600 ppp', puce=''))

etat_b = f'''
  <h2>Etat B &mdash; un lot designe, le panneau replie, et un media qui attend</h2>
  <div class="app">
    <div class="app-header"><span class="app-title">Scan</span></div>
    <div class="app-body">
      <div class="nav pli">
        <div class="nav-head"><span class="pl">&#8677;</span></div>
        <div class="tree">{nav('lot')}</div>
      </div>
      <div class="bin">
        <div class="bin-head"><span class="bin-scope">Chutier</span><span class="plein">plein ecran</span></div>
        <div class="portee">Contenu de <b>Extraction 12,5 fps</b> &middot; 1 planche</div>
        <div class="filtres"><span class="tog"><span class="car">&#9662;</span>Filtres</span><span class="cur">scans</span></div>
        <div class="filtres-open">
          <span class="filtre">Tout</span><span class="filtre on">Scans</span><span class="filtre">Planches</span><span class="filtre">Exports</span>
        </div>
        <div class="queue">
          <div class="queue-title"><span>En attente de lecture</span><span class="meta">1</span></div>
          <div class="chk"><span class="puce"></span><span class="mono">scan-recu.tif</span><span class="sig libre" title="Confirme comme scan. Il attend le decodage de son QR.">?</span></div>
        </div>
        <div class="tree">{chutier_b}</div>
        <div class="bulle" style="left:96px; top:330px">
          <b>&#9888; Incomplet</b> &mdash; 7 frames sur 9. Les pages 8 et 9 n'ont pas ete scannees.
        </div>
      </div>
      <div class="work">
        <div class="scrim">
          <div class="fen">
            <h4>Que viens-tu de deposer ?</h4>
            <span class="file">planche-recue.pdf</span>
            <p>Planche a imprimer, ou scan d'une planche ?</p>
            <div class="row2">
              <button class="btn ghost" type="button">C'est un scan</button>
              <button class="btn" type="button">C'est une planche a imprimer</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  <p class="caption">Repondre « c'est un scan » ne le range pas : il rejoint la file d'attente de
  lecture, et il en sortira quand son QR aura ete decode &mdash; ou quand on lui aura designe un
  parent a la main.</p>
'''

HTML = f'''<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chutier v2 — maquette d'ecran cle</title>
<style>
/* ===========================================================================
   MAQUETTE D'ECRAN CLE — LE CHUTIER, VERSION 2, REVISION DU 21 AOUT
   Six retours d'Egan appliques : pictogrammes au lieu de lettres, chrome
   allege, + / - au lieu de la fleche, puce de selection a trois etats, traits
   d'arbre qui s'arretent au dernier objet, metadonnees justes. Plus deux
   retours sur l'etat B : la remarque n'est pas un objet de l'arbre, et
   l'import ouvre une fenetre.
   Arbitrages portes : EPIC7-ARB-3, 4, 9, 10, 11, 13, 14 et A2.
   Invariants : neutres R=G=B, la couleur ne porte jamais seule, l'accent ne
   s'approche pas d'une zone d'image.
   =========================================================================== */
{TOKENS}
{CSS}
</style>
</head>
<body>
<div class="sheet">

  <h1>Le chutier, version 2</h1>
  <p class="sub">Revision du 21 aout : le chrome s'allege &mdash; plus de cartouche, plus de trait
  d'accent, plus de fleche &mdash; et ce qui reste porte du sens. <b class="k">La puce dit la
  selection</b>, <b class="k">le signe + dit qu'il y a des enfants</b>, et son absence dit qu'il
  n'y en a pas.</p>
{etat_a}
{etat_b}
  <div class="legend">
    <span><span class="puce all"></span> tous les enfants selectionnes</span>
    <span><span class="puce some"></span> selection ponctuelle</span>
    <span><span class="sig incomplet">&#9888;</span> incomplet</span>
    <span><span class="sig libre">?</span> non rattache</span>
    <span><span class="sig delie">&#8856;</span> delie</span>
  </div>

</div>
</body>
</html>
'''
(M / 'key-chutier-v2.html').write_text(HTML, encoding='utf-8')
print(f'{(M / "key-chutier-v2.html").stat().st_size/1024:.0f} Ko')
