#!/usr/bin/env python3
"""Le point d'entree UNIQUE pour lancer, lire et arreter une suite de tests.

**Pourquoi ce module existe, et ce qu'il a coute de ne pas l'avoir.** Le
2026-08-31, la mesure de `coeur/arb-89-sorties-nommees` contre `origin/main` a
ete relancee **quatre fois** et a coute plus de trois heures d'attente, pour
quatre raisons distinctes qui sont exactement les quatre choses que ce module
ferme :

1. **un plafond global tuait la course entiere.** `timeout 5400 pytest ...` a
   rendu `EXIT=124` a 80 %. Un seul test qui suspend emportait les 7000 autres ;
2. **la sortie n'etait pas lisible en cours de route.** En `-q`, pytest ne nomme
   les rouges qu'a la toute fin : 90 minutes de calcul pour une sortie sans une
   seule liste exploitable. Et lire le journal brut coute des milliers de lignes
   de contexte a l'agent qui le consulte ;
3. **un agent a tue ses propres mesures**, trois fois, avec un `pkill` par motif
   qui n'a jamais su distinguer le process a tuer de celui qui venait d'etre
   lance ;
4. **rien n'etait mesure**, donc rien ne tenait : chaque session reinventait sa
   ligne de commande, et la reinventait differemment.

La reponse est un outil, pas une consigne. Une consigne se rappelle et se perd ;
un point d'entree unique s'appelle ou ne s'appelle pas, et
`tests/unit/test_outillage_de_mesure.py` mesure qu'il tient ses promesses.

Les quatre garanties, dans l'ordre ou Egan les a demandees :

* **rapide** -- ordre deterministe (`-p no:randomly`) et parallelisme **par
  defaut**, autant de process que de coeurs, depuis la mesure du 2026-09-01 :
  la suite entiere passe de 2 h 28 a 55 min, et les listes de verdicts d'une
  course serie et de DEUX courses `-n 4` sont identiques au condensat pres,
  6846 tests de chaque cote. `--parallele 0` rend la serie explicitement. Les
  25 tests les plus lents restent enregistres a chaque course : ils disent que
  29,6 % du temps de la suite tient dans 25 tests sur 6846, tous dans le meme
  chemin de decodage QR -- c'est la que se trouve la prochaine acceleration, et
  elle vaut mieux qu'un coeur de plus ;
* **lisible en cours de route** -- `etat` rend une vingtaine de lignes bornees :
  avancement, cardinaux, et les NOMS des rouges. Il ne rend JAMAIS le journal ;
* **ne peut pas couper par defaut** -- il n'y a **aucun** plafond global. Le
  plafond est PAR TEST (`--timeout`). Un plafond global n'existe que si on le
  demande a la main.

  **Portee exacte de cette garantie, mesuree le 2026-08-31 et non plus
  supposee.** `--timeout-method=thread` tue le PROCESS au depassement. En
  serie, la course s'arrete donc au premier test qui suspend -- la promesse
  « il meurt seul et la course continue » etait fausse, elle est ici corrigee.
  Sous xdist, seul le worker meurt et xdist le remplace : la course continue
  vraiment. La methode `signal`, elle, laisserait la course continuer en serie,
  mais n'attrape PAS le blocage reel de ce depot (`decode_qr_image_resilient`
  reste dans `cv2` en gardant le GIL, donc `SIGALRM` n'est jamais delivre).
  C'est la premiere des deux raisons pour lesquelles le parallelisme n'est pas
  qu'une acceleration ici ;
* **sur vis-a-vis des agents** -- la course part dans son PROPRE groupe de
  process, dont l'identifiant est ecrit sur disque au lancement. `arreter` tue
  ce groupe-la et rien d'autre : il n'y a pas un seul motif dans ce fichier.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import NamedTuple

#: La racine du depot, deduite de l'emplacement de ce fichier et jamais du
#: repertoire courant -- un agent lance ses commandes de n'importe ou.
RACINE = Path(__file__).resolve().parent.parent.parent

#: Ou vivent les courses. Ignore par git : ce sont des mesures, pas des sources.
DOSSIER_DES_COURSES = Path(
    os.environ.get("MESURE_DOSSIER_DES_COURSES", RACINE / ".mesures")
)

#: Le plafond PAR TEST, en secondes. Il ne tue jamais que le test qui suspend.
#: 300 s est large pour ce depot : le test le plus lent mesure y tient
#: confortablement, et un test qui depasse cinq minutes est un defaut a voir.
PLAFOND_PAR_TEST_PAR_DEFAUT = 300

#: Le parallelisme est le DEFAUT depuis la mesure du 2026-09-01, et il l'est
#: sur une mesure, pas sur une intuition. Protocole : suite entiere (6846
#: tests), machine au repos, arbre fige sur un seul commit, meme exclusion des
#: deux cotes ; une course en serie, DEUX courses a `-n 4`. Les trois listes de
#: verdicts -- tous les tests, pas seulement les rouges -- sont IDENTIQUES au
#: condensat pres, et les trois courses jouent 6846 tests. Zero faux rouge,
#: zero test perdu, deux fois de suite.
#:
#:     serie   2 h 28 min 11 s
#:     para-1  0 h 55 min 36 s   (x 2,67)
#:     para-2  0 h 54 min 45 s   (x 2,71)
#:
#: `--parallele 0` reste la sortie explicite vers la serie -- jamais un blocage
#: sec, meme doctrine qu'`EPIC11-ARB-89`. Elle sert a lire une trace propre
#: quand on chasse UN rouge, ce que quatre workers entrelacent.
PARALLELISME_PAR_DEFAUT_EST_LE_NOMBRE_DE_COEURS = True

#: Le nombre de noms de rouges que `etat` cite avant de s'arreter et d'annoncer
#: le reste par un cardinal. La borne est le coeur de la promesse de lisibilite:
#: une sortie d'etat ne doit jamais pouvoir ruiner le contexte de son lecteur.
NOMS_CITES_AU_MAXIMUM = 15

#: Ce que `lancer` dit a l'agent, a chaque lancement, parce qu'une consigne qui
#: vit ailleurs ne se lit pas au moment ou elle sert. Mesure du 2026-09-01 :
#: DEUX courses de la suite entiere perdues, mortes toutes deux a 41 %, et une
#: troisieme terminee sur le MEME arbre parce que l'agent etait reste en veille.
#: Le cout reel n'est pas le calcul jete, c'est le FAUX DIAGNOSTIC : deux morts
#: au meme pourcentage ressemblent a s'y meprendre a une regression du code.
AVERTISSEMENT_DE_VEILLE_ACTIVE = """
  ATTENTION -- cette course PEUT etre suspendue si tu rends la main.
  Mesure : deux courses mortes ~4 min apres la fin du tour de leur agent,
  SANS aucune trace -- ni erreur, ni `node down`, ni resume pytest. Mais deux
  autres, sur un autre conteneur, ont survecu pres de DEUX HEURES au repos et
  sont allees jusqu'au bout : la cause n'est pas isolee, seule la panne l'est.
  Reste donc en veille active, et surtout lis `etat`, qui dit MUETTE DEPUIS N
  quand le journal se tait plus longtemps que le plafond par test. Attente
  bornee dans l'appel courant :
      for i in $(seq 1 110); do
        tail -8 <journal> | grep -qE '={3,}.*(passed|failed|error)' && break
        sleep 5
      done
  Et ne conclus JAMAIS d'une course morte sans avoir lu l'HORODATAGE de
  derniere ecriture du journal (`stat -c %y <journal>`, ou la ligne MUETTE
  DEPUIS d'`etat`). Le temps ecoule qu'affiche `etat` court depuis le
  LANCEMENT : il continue apres la mort, et il a deja fait conclure faux.
  Un compteur qui court n'est pas un producteur vivant."""

#: La ligne que la course ecrit en queue de journal quand elle a rendu la main.
#: `etat` s'en sert pour distinguer « en cours » de « terminee ».
MARQUEUR_DE_FIN = "MESURE-TERMINEE="

_VERDICTS_ROUGES = ("FAILED", "ERROR")
_VERDICTS_CONNUS = "PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS"

#: pytest ecrit ses verdicts sous **deux** formes, et le depouilleur n'en
#: connaissait qu'une. C'est le defaut le plus couteux trouve le 2026-08-31 :
#: `rouges` rendait une liste VIDE pour toute course parallele -- mesure, sur
#: une course `-n 4` de la suite entiere : 0 rouge vu la ou il y en avait 16 sur
#: 1991 tests. Le protocole de comparaison lui-meme (`rouges serie` contre
#: `rouges para`, puis `diff`) aurait donc valide le parallelisme **par
#: l'incapacite de l'outil a voir ses echecs**. Un faux vert coute plus cher
#: qu'un faux rouge : le second envoie chercher, le premier certifie.
#:
#: **Le nom d'un test peut contenir des espaces**, et c'est le deuxieme trou du
#: depouilleur, trouve le 2026-09-01 en confrontant son compte a celui de
#: pytest. Un test parametre porte son parametre dans son identifiant, et ce
#: depot en a 139 qui contiennent une espace :
#:     ...::test_un_code_sans_rien_d_exploitable_vaut_absent[blancs melanges]
#:     ...::test_les_TROIS_AUTRES_touches[110-attendu0-n suivante]
#: Un motif en `\S+::\S+` les traitait de deux facons OPPOSEES selon le
#: regime : en serie il ne les appariait pas du tout (139 tests perdus), en
#: parallele il en gardait une version TRONQUEE au premier espace -- donc des
#: noms faux, et jusqu'a des doublons fantomes quand deux parametres tronquaient
#: pareil (11 sur la course `p1`). Asymetrique, donc **fabriquant un ecart
#: entre les deux regimes la ou il n'y en avait aucun** : exactement le faux
#: rouge que cette mesure devait chercher, produit par l'instrument.
#:
#: Le nom court donc jusqu'au verdict, et le verdict est ancre sur ce qui le
#: suit toujours : le pourcentage en serie, la fin de ligne sous xdist.
#:
#: En serie -- le nom d'abord, le verdict ensuite :
#:     tests/unit/x.py::test_y[deux mots] PASSED               [ 12%]
_LIGNE_EN_SERIE = re.compile(
    rf"^(?P<test>\S+::.*?)\s+(?P<verdict>{_VERDICTS_CONNUS})\s+\[\s*\d+%\]"
)
#: Sous xdist -- le worker d'abord, puis l'avancement, puis le verdict AVANT le
#: nom. Rien de commun avec la precedente que le nom du verdict lui-meme :
#:     [gw2] [  0%] PASSED tests/unit/x.py::test_y[deux mots]
_LIGNE_EN_PARALLELE = re.compile(
    rf"^\[gw\d+\]\s+\[\s*\d+%\]\s+(?P<verdict>{_VERDICTS_CONNUS})"
    rf"\s+(?P<test>\S+::.*?)\s*$"
)

#: La derniere ligne que pytest ecrit, et le seul temoin exterieur dont le
#: depouilleur dispose : `==== 209 failed, 6517 passed, 11 skipped, 109 errors
#: in 8891.04s ====`. S'y confronter est ce qui a revele les deux trous
#: ci-dessus -- un depouilleur qui ne se compare a rien ne peut pas savoir
#: qu'il ne voit pas tout.
_TOTAUX_DE_PYTEST = re.compile(
    r"(\d+) (failed|passed|skipped|error|xfailed|xpassed)s?\b"
)


class Depouille(NamedTuple):
    """Ce qu'un journal apprend, sans jamais avoir a le rendre en entier.

    `verdicts` associe un test a **son** verdict, la ou `cardinaux` compte des
    LIGNES. Les deux ne coincident pas toujours : un test peut etre annonce
    deux fois (echec au demontage apres un appel vert, reprise d'un test dont
    le worker est mort). L'ecart entre `len(verdicts)` et le total des
    cardinaux est donc une information, pas une erreur d'arrondi -- et c'est
    exactement ce qu'il faut regarder pour savoir si un regime a PERDU des
    tests en route.
    """

    cardinaux: dict[str, int]
    rouges: list[str]
    avancement: int
    verdicts: dict[str, str]
    total_annonce_par_pytest: int | None


def _verdict_de_la_ligne(ligne: str):
    """Le couple (test, verdict) d'une ligne, quelle que soit sa forme."""
    trouve = _LIGNE_EN_SERIE.match(ligne) or _LIGNE_EN_PARALLELE.match(ligne)
    if trouve is None:
        return None
    return trouve.group("test"), trouve.group("verdict")


def dossier_de_la_course(nom: str) -> Path:
    """Le dossier d'une course, un nom valant un identifiant stable."""
    if not re.fullmatch(r"[a-zA-Z0-9._-]{1,64}", nom):
        raise SystemExit(
            f"Nom de course invalide: {nom!r}. Attendu: lettres, chiffres, "
            "point, tiret ou souligne, 64 caracteres au plus."
        )
    return DOSSIER_DES_COURSES / nom


def _groupe_vivant(pgid: int) -> bool:
    """Vrai si le groupe de process existe encore.

    Le signal 0 ne tue rien : il ne fait que poser la question au noyau. C'est
    la seule facon honnete de savoir si une course tourne -- compter des lignes
    de journal ne dit pas si le producteur est vivant.
    """
    try:
        os.killpg(pgid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _pgid_de_la_course(dossier: Path) -> int | None:
    fichier = dossier / "pgid"
    if not fichier.is_file():
        return None
    try:
        return int(fichier.read_text().strip())
    except ValueError:
        return None


def lancer(args: argparse.Namespace) -> int:
    """Demarre une course, dans son propre groupe de process."""
    dossier = dossier_de_la_course(args.nom)

    # Une course vivante ne se recouvre pas : deux suites sur le meme nom se
    # disputent le journal ET le CPU. C'est arrive, et c'est ce qui a rendu les
    # sorties partielles du 2026-08-31 incomparables entre elles.
    pgid_en_place = _pgid_de_la_course(dossier)
    if pgid_en_place is not None and _groupe_vivant(pgid_en_place):
        print(
            f"La course {args.nom!r} tourne deja (groupe {pgid_en_place}). "
            f"L'arreter par `mesure.py arreter {args.nom}` ou choisir un autre "
            "nom.",
            file=sys.stderr,
        )
        return 2

    if dossier.exists():
        shutil.rmtree(dossier)
    dossier.mkdir(parents=True)

    # Le greffon du plafond par test doit etre la, sinon pytest refuse l'option
    # et la course ne part pas du tout. On le dit AVANT de lancer, en nommant
    # les deux issues -- jamais un blocage sec (meme doctrine qu'EPIC11-ARB-89).
    if args.plafond_par_test > 0 and importlib.util.find_spec("pytest_timeout") is None:
        print(
            "Le greffon `pytest-timeout` manque, et c'est lui qui porte le "
            "plafond PAR TEST. Deux issues, au choix :\n"
            "  * l'installer  : pip install pytest-timeout   (recommande)\n"
            "  * s'en passer  : --plafond-par-test 0         (un test qui "
            "suspend bloquera alors la course entiere)",
            file=sys.stderr,
        )
        return 2
    # Le parallelisme etant desormais le defaut, l'absence du greffon n'est plus
    # un detail de configuration : elle change ce qui va tourner. On nomme les
    # deux issues plutot que de bloquer sec, et on nomme aussi le prix de la
    # seconde -- 2 h 28 contre 55 min, mesure.
    veut_du_parallelisme = args.parallele is None or args.parallele > 1
    if veut_du_parallelisme and importlib.util.find_spec("xdist") is None:
        print(
            "Le greffon `pytest-xdist` manque, et le parallelisme est le "
            "defaut depuis le 2026-09-01. Deux issues, au choix :\n"
            "  * l'installer : pip install pytest-xdist   (recommande)\n"
            "  * s'en passer : --parallele 0              (la suite entiere "
            "passe alors de 55 min a 2 h 28, mesure)",
            file=sys.stderr,
        )
        return 2

    commande = _commande_pytest(args)
    (dossier / "commande.txt").write_text(" ".join(commande) + "\n", encoding="utf-8")

    environnement = dict(os.environ)
    environnement.setdefault("PYTHONPATH", "src")
    # Les bancs Qt tournent hors ecran : sans cela ils echouent ou suspendent,
    # ce qui est precisement le genre de panne que l'on cherche a exclure.
    environnement.setdefault("QT_QPA_PLATFORM", "offscreen")

    journal = dossier / "journal.txt"
    with journal.open("w", encoding="utf-8") as sortie:
        processus = subprocess.Popen(
            commande,
            cwd=str(args.depuis or RACINE),
            stdout=sortie,
            stderr=subprocess.STDOUT,
            env=environnement,
            # LA garantie de surete : `setsid` met la course dans son propre
            # groupe. `arreter` vise ce groupe par son identifiant, donc il ne
            # peut pas emporter une course voisine -- ni une course qu'un autre
            # agent vient de lancer.
            start_new_session=True,
        )

    (dossier / "pid").write_text(f"{processus.pid}\n", encoding="utf-8")
    (dossier / "pgid").write_text(f"{os.getpgid(processus.pid)}\n", encoding="utf-8")
    (dossier / "depart").write_text(f"{time.time()}\n", encoding="utf-8")

    print(f"Course {args.nom!r} lancee.")
    print(f"  groupe de process : {os.getpgid(processus.pid)}")
    print(f"  journal           : {journal}")
    print(f"  lire l'avancement : scripts/mesure/mesure.py etat {args.nom}")
    print(f"  arreter           : scripts/mesure/mesure.py arreter {args.nom}")
    print(AVERTISSEMENT_DE_VEILLE_ACTIVE)
    return 0


def _commande_pytest(args: argparse.Namespace) -> list[str]:
    """La ligne de commande, construite en un seul endroit.

    Elle ne porte **aucun** plafond global : c'est le point 3 de la promesse.
    Le seul plafond est `--timeout`, qui est par test.
    """
    commande = [
        sys.executable,
        "-m",
        "pytest",
        *(args.cibles or ["tests"]),
        # `-v` et non `-q` : les noms sortent au fil de l'eau, donc le journal
        # est exploitable meme si la course est interrompue. C'est ce qui a
        # manque le 2026-08-31, ou 90 minutes de `-q` n'ont rien nomme.
        "-v",
        # Pas de traceback dans le journal : `etat` a besoin des NOMS, et une
        # trace par rouge fait exploser le fichier sans rien apprendre de plus.
        "--tb=no",
        # Ordre deterministe : deux courses comparees doivent parcourir la meme
        # sequence, sinon leurs sorties partielles ne se comparent pas.
        "-p",
        "no:randomly",
        # Les 25 plus lents, toujours : l'acceleration suivante se fondera sur
        # cette mesure et pas sur une intuition.
        "--durations=25",
    ]
    if args.plafond_par_test > 0:
        commande += [
            f"--timeout={args.plafond_par_test}",
            # `thread` interrompt le test sans tuer le process : le reste de la
            # course survit a un test qui suspend.
            "--timeout-method=thread",
        ]
    # `None` = personne n'a tranche, donc le defaut mesure s'applique : autant
    # de process que de coeurs. On ecrit le NOMBRE dans la commande, jamais le
    # mot-cle `auto` d'xdist : `commande.txt` est ce que relira la session
    # suivante pour rejouer la meme course, et « auto » ne dit pas ce qui a
    # tourne.
    parallele = args.parallele
    if parallele is None:
        parallele = os.cpu_count() or 1
    if parallele > 1:
        commande += ["-n", str(parallele)]
    commande += list(args.options_supplementaires or [])
    return commande


def _lire_les_verdicts(journal: Path) -> Depouille:
    """Depouille le journal : cardinaux, verdicts par test, avancement.

    Le depouillement se fait en UN passage et ne garde jamais le journal en
    memoire -- un journal de 7000 lignes ne doit pas devenir 7000 lignes de
    contexte pour qui le lit.

    Deux formes de ligne sont reconnues, la serie et xdist. Voir le commentaire
    de `_LIGNE_EN_PARALLELE` : n'en connaitre qu'une rendait `rouges` muet sur
    toute course parallele, donc capable de certifier un parallelisme qu'il ne
    savait pas observer.

    **Le rouge l'emporte sur le vert quand un test est annonce deux fois.** Un
    test peut passer son appel puis echouer a son demontage, ou etre repris
    apres la mort de son worker. Garder le DERNIER verdict ferait disparaitre un
    rouge derriere une reprise verte, ce qui est precisement le genre de silence
    que cet outil existe pour empecher.
    """
    cardinaux: dict[str, int] = {}
    verdicts: dict[str, str] = {}
    avancement = 0
    annonce: int | None = None
    if not journal.is_file():
        return Depouille(cardinaux, [], avancement, verdicts, annonce)
    with journal.open(encoding="utf-8", errors="replace") as flux:
        for ligne in flux:
            couple = _verdict_de_la_ligne(ligne)
            if couple is not None:
                test, verdict = couple
                cardinaux[verdict] = cardinaux.get(verdict, 0) + 1
                if verdicts.get(test) not in _VERDICTS_ROUGES:
                    verdicts[test] = verdict
            elif ligne.startswith("=") and " in " in ligne:
                comptes = _TOTAUX_DE_PYTEST.findall(ligne)
                if comptes:
                    annonce = sum(int(n) for n, _ in comptes)
            pourcent = re.search(r"\[\s*(\d+)%\]", ligne)
            if pourcent is not None:
                avancement = int(pourcent.group(1))
    rouges = [
        f"{verdict} {test}"
        for test, verdict in verdicts.items()
        if verdict in _VERDICTS_ROUGES
    ]
    return Depouille(cardinaux, rouges, avancement, verdicts, annonce)


def _plafond_de_la_course(dossier: Path) -> int:
    """Le plafond par test de CETTE course, relu de sa propre commande.

    On ne suppose pas le defaut : une course lancee avec `--plafond-par-test 0`
    n'a pas le meme silence normal qu'une course a 300 s. Le seuil de silence
    se deduit donc de ce qui a REELLEMENT tourne, pas d'une constante.
    """
    fichier = dossier / "commande.txt"
    if not fichier.is_file():
        return PLAFOND_PAR_TEST_PAR_DEFAUT
    trouve = re.search(r"--timeout=(\d+)", fichier.read_text(errors="replace"))
    return int(trouve.group(1)) if trouve else 0


def _silence_du_journal(dossier: Path) -> tuple[int, int] | None:
    """L'age de la derniere ecriture du journal, et le seuil au-dela duquel
    ce silence n'est plus explicable par un test lent.

    **Pourquoi cette mesure existe** (2026-09-01). Une course en tache de fond
    peut cesser d'ecrire sans laisser la moindre trace : ni erreur, ni
    `node down`, ni resume pytest. Or `etat` affichait jusqu'ici un temps
    ecoule depuis le LANCEMENT, qui continue de courir apres la mort -- et deux
    lecteurs successifs, dont l'auteur de ce module, en ont conclu des choses
    fausses. Un compteur qui court n'est pas un producteur vivant : c'est ce que
    `_groupe_vivant` disait deja du cardinal des lignes, applique au temps.

    Le seuil est le plafond PAR TEST de la course, et ce choix n'est pas
    arbitraire : en deca, un silence s'explique par un test lent ; au-dela, il
    ne s'explique plus, puisque ce test aurait ete interrompu. Sans plafond, on
    ne peut rien affirmer -- la fonction rend alors un seuil nul, et l'appelant
    n'annonce rien plutot que d'inventer une alerte.
    """
    journal = dossier / "journal.txt"
    if not journal.is_file():
        return None
    return int(time.time() - journal.stat().st_mtime), _plafond_de_la_course(dossier)


def etat(args: argparse.Namespace) -> int:
    """Rend l'etat d'une course en une vingtaine de lignes, jamais plus."""
    dossier = dossier_de_la_course(args.nom)
    if not dossier.is_dir():
        print(f"Aucune course nommee {args.nom!r}.", file=sys.stderr)
        return 2

    pgid = _pgid_de_la_course(dossier)
    vivante = pgid is not None and _groupe_vivant(pgid)
    releve = _lire_les_verdicts(dossier / "journal.txt")
    cardinaux, rouges, avancement = releve.cardinaux, releve.rouges, releve.avancement
    verdicts = releve.verdicts

    depart = dossier / "depart"
    ecoule = ""
    if depart.is_file():
        try:
            ecoule = f", {int(time.time() - float(depart.read_text().strip()))} s ecoulees"
        except ValueError:
            ecoule = ""

    # On compte les TESTS DISTINCTS, pas les lignes : c'est ce cardinal-la qui
    # se compare d'un regime a l'autre. Quand les deux different, on le dit --
    # l'ecart signale une reprise ou un echec de demontage, jamais un arrondi.
    annonce = f"{len(verdicts)} tests joues"
    if sum(cardinaux.values()) != len(verdicts):
        annonce += f" ({sum(cardinaux.values())} lignes de verdict)"
    lignes = [
        f"course {args.nom} : {'EN COURS' if vivante else 'ARRETEE'}"
        f" (groupe {pgid}{ecoule})",
        f"avancement : {avancement} % -- {annonce}",
        "cardinaux  : "
        + (", ".join(f"{v} {c}" for v, c in sorted(cardinaux.items())) or "aucun"),
    ]
    # Le journal se tait-il ? C'est la seule facon de distinguer une course
    # vivante et lente d'une course morte sans un mot -- et le temps ecoule
    # depuis le lancement, lui, ne le dit pas : il court dans les deux cas.
    # Une course TERMINEE se tait forcement : pytest a ecrit son resume et
    # rendu la main. Confondre les deux ferait crier l'alerte sur toutes les
    # courses finies, et une alerte qui crie toujours ne se lit plus. Le
    # discriminant est celui qui existe deja : pytest a-t-il ecrit son total ?
    silence = _silence_du_journal(dossier)
    terminee = releve.total_annonce_par_pytest is not None
    if silence is not None:
        age, seuil = silence
        if terminee:
            lignes.append("journal    : course terminee, pytest a ecrit son total")
        elif seuil > 0 and age > seuil:
            lignes.append(
                f"MUETTE DEPUIS {age // 60} min {age % 60} s -- au-dela du "
                f"plafond par test ({seuil} s), ce silence ne s'explique plus "
                "par un test lent. Verifier le groupe avant de conclure quoi "
                "que ce soit de l'avancement ci-dessus."
            )
        else:
            lignes.append(f"journal    : derniere ecriture il y a {age} s")

    # Le seul temoin exterieur dont dispose le depouilleur. Deux trous de
    # lecture ont ete trouves par cette confrontation le 2026-09-01, et aucun
    # test positif ne pouvait les voir : un depouilleur qui ne se compare a
    # rien ne sait pas qu'il ne voit pas tout.
    attendu = releve.total_annonce_par_pytest
    if attendu is not None and attendu != sum(cardinaux.values()):
        lignes.append(
            f"DESACCORD  : pytest annonce {attendu} verdicts, "
            f"{sum(cardinaux.values())} ont ete lus. Le depouilleur est "
            "aveugle a une forme de ligne -- ne PAS comparer deux courses "
            "tant que ce nombre n'est pas nul."
        )
    if rouges:
        lignes.append(f"rouges     : {len(rouges)}")
        for nom in rouges[:NOMS_CITES_AU_MAXIMUM]:
            lignes.append(f"  {nom}")
        if len(rouges) > NOMS_CITES_AU_MAXIMUM:
            reste = len(rouges) - NOMS_CITES_AU_MAXIMUM
            lignes.append(
                f"  ... et {reste} autres, listes par "
                f"`mesure.py rouges {args.nom}`"
            )
    else:
        lignes.append("rouges     : aucun a ce stade")
    print("\n".join(lignes))
    return 0


def rouges(args: argparse.Namespace) -> int:
    """La liste COMPLETE des rouges, triee -- c'est elle qu'on compare.

    Deliberement separee de `etat` : `etat` est borne parce qu'on le consulte
    souvent ; cette sortie-ci ne se demande qu'au moment de conclure.
    """
    dossier = dossier_de_la_course(args.nom)
    for ligne in sorted(_lire_les_verdicts(dossier / "journal.txt").rouges):
        print(ligne)
    return 0


def verdicts(args: argparse.Namespace) -> int:
    """TOUS les verdicts, un par test, tries -- la comparaison la plus forte.

    Ajoute le 2026-08-31, sur la mesure du parallelisme. Comparer les seules
    listes de rouges laisse passer une divergence entiere : un test VERT d'un
    cote et SAUTE de l'autre ne figure dans aucune des deux listes, et xdist
    peut perdre des tests en silence. Le cardinal des lignes de cette sortie
    est aussi le cardinal des tests joues, donc le `diff` de deux `verdicts`
    repond d'un seul geste aux deux questions posees : memes verdicts, et
    autant de tests des deux cotes.
    """
    dossier = dossier_de_la_course(args.nom)
    releve = _lire_les_verdicts(dossier / "journal.txt")
    for test, verdict in sorted(releve.verdicts.items()):
        print(f"{verdict} {test}")
    return 0


def arreter(args: argparse.Namespace) -> int:
    """Arrete une course, et **seulement** celle-la.

    Il n'y a pas un seul motif dans cette fonction. On tue un groupe de process
    dont l'identifiant a ete ecrit au lancement -- par identite, jamais par
    ressemblance (regle `arret-de-process-par-identite` de CLAUDE.md).
    """
    dossier = dossier_de_la_course(args.nom)
    pgid = _pgid_de_la_course(dossier)
    if pgid is None:
        print(
            f"Pas de groupe enregistre pour {args.nom!r} : rien n'est arrete. "
            "C'est voulu -- sans identifiant, on ne devine pas une cible.",
            file=sys.stderr,
        )
        return 2
    if not _groupe_vivant(pgid):
        print(f"La course {args.nom!r} (groupe {pgid}) est deja arretee.")
        return 0
    os.killpg(pgid, signal.SIGTERM)
    for _ in range(20):
        if not _groupe_vivant(pgid):
            print(f"Course {args.nom!r} arretee (groupe {pgid}).")
            return 0
        time.sleep(0.5)
    os.killpg(pgid, signal.SIGKILL)
    print(f"Course {args.nom!r} arretee de force (groupe {pgid}).")
    return 0


def lister(_args: argparse.Namespace) -> int:
    """Les courses connues et leur etat, une ligne chacune."""
    if not DOSSIER_DES_COURSES.is_dir():
        print("Aucune course.")
        return 0
    for dossier in sorted(DOSSIER_DES_COURSES.iterdir()):
        if not dossier.is_dir():
            continue
        pgid = _pgid_de_la_course(dossier)
        vivante = pgid is not None and _groupe_vivant(pgid)
        releve = _lire_les_verdicts(dossier / "journal.txt")
        print(
            f"{dossier.name:24s} {'EN COURS' if vivante else 'ARRETEE ':9s} "
            f"{releve.avancement:3d} % {len(releve.verdicts):6d} joues "
            f"{len(releve.rouges):4d} rouges"
        )
    return 0


def construire_l_analyseur() -> argparse.ArgumentParser:
    analyseur = argparse.ArgumentParser(
        prog="mesure.py",
        description=(
            "Lance, lit et arrete une suite de tests. Point d'entree UNIQUE: "
            "aucune session ne reecrit sa propre ligne de commande pytest."
        ),
    )
    sous = analyseur.add_subparsers(dest="geste", required=True)

    p = sous.add_parser("lancer", help="demarrer une course en tache de fond")
    p.add_argument("nom", help="identifiant de la course, ex: branche ou main")
    p.add_argument("cibles", nargs="*", help="chemins pytest (defaut: tests)")
    p.add_argument(
        "--plafond-par-test",
        type=int,
        default=PLAFOND_PAR_TEST_PAR_DEFAUT,
        help=(
            "secondes accordees a UN test avant qu'il soit interrompu seul "
            f"(defaut {PLAFOND_PAR_TEST_PAR_DEFAUT}; 0 pour aucun plafond). "
            "Il n'existe deliberement AUCUN plafond global."
        ),
    )
    p.add_argument(
        "--parallele",
        type=int,
        default=None,
        help=(
            "nombre de process pytest-xdist. Par defaut : autant que de "
            "coeurs, depuis la mesure du 2026-09-01 (suite entiere, une "
            "course serie et deux courses -n 4, listes de verdicts identiques "
            "au condensat pres, x 2,7). `--parallele 0` rend la serie, "
            "explicitement : c'est la sortie a prendre pour lire une trace "
            "propre quand on chasse UN rouge."
        ),
    )
    p.add_argument("--depuis", help="repertoire de lancement (defaut: la racine)")
    p.add_argument(
        "--options-supplementaires",
        action="append",
        metavar="OPTION",
        help=(
            "UNE option pytest ajoutee telle quelle, en dernier. A repeter "
            "pour en passer plusieurs. Trouve inutilisable le 2026-08-31 : en "
            "`nargs=\"*\"`, argparse refuse toute valeur commencant par un "
            "tiret -- c'est-a-dire TOUTES les options pytest, le seul usage de "
            "ce drapeau. `--options-supplementaires=--ignore=X` passait, mais "
            "une seule fois et seulement avec le signe egal."
        ),
    )
    p.set_defaults(fonction=lancer)

    p = sous.add_parser("etat", help="avancement borne, sans lire le journal")
    p.add_argument("nom")
    p.set_defaults(fonction=etat)

    p = sous.add_parser("rouges", help="liste complete et triee des rouges")
    p.add_argument("nom")
    p.set_defaults(fonction=rouges)

    p = sous.add_parser(
        "verdicts",
        help="TOUS les verdicts, un par test : la comparaison la plus forte",
    )
    p.add_argument("nom")
    p.set_defaults(fonction=verdicts)

    p = sous.add_parser("arreter", help="arreter une course par son groupe")
    p.add_argument("nom")
    p.set_defaults(fonction=arreter)

    p = sous.add_parser("lister", help="toutes les courses connues")
    p.set_defaults(fonction=lister)

    return analyseur


def main(argv: list[str] | None = None) -> int:
    args = construire_l_analyseur().parse_args(argv)
    try:
        return int(args.fonction(args))
    except BrokenPipeError:
        # `etat | head` est l'usage NORMAL de cet outil, et il casse le tube des
        # que le lecteur a lu ce qu'il voulait. Trouve a l'essai de bout en bout
        # du 2026-08-31 : sans ce rattrapage, une consultation d'avancement
        # rendait une trace Python de dix lignes -- soit precisement le bruit de
        # contexte que ce module existe pour supprimer.
        try:
            sys.stdout.close()
        except BrokenPipeError:
            pass
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
