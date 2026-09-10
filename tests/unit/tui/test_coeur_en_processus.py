# -*- coding: utf-8 -*-
"""Story 11.0, AC 5 et AC 7 -- le coeur est heberge, et il n'a pas bouge."""

import ast
import subprocess
import tempfile
from pathlib import Path

import pytest
from textual.widgets import Static

from mixed_media_utility.io.naming import CANONICAL_ID_MAX_LENGTH, derive_short_id
from mixed_media_utility.tui.coque import CoqueTui

from outils_frontiere import identifiants

#: Tout ce par quoi un second processus pourrait naitre. La liste est celle de
#: l'AC 5.2, nom pour nom.
LANCEURS_INTERDITS = ("subprocess", "Popen", "system", "execv", "execvp",
                      "execl", "spawnv", "fork")

#: **Tolerance documentee**, meme forme et meme statut que
#: `CHANGEMENTS_ACCEPTES` ci-dessous : ce n'est pas un affaiblissement
#: silencieux de la garde, c'est un arbitrage ecrit AVEC son motif.
#:
#: `EPIC11-ARB-85` (2026-08-30, reponse a `Q9` du lot `K3` de la 11.4) : le
#: motif de l'AC 5.2 est `EPIC11-ARB-1`, « le coeur est heberge, pas relance »
#: -- ne pas re-invoquer `mmu` en sous-processus pour faire le travail du
#: coeur. **Remettre un dossier au bureau ne fait aucun travail du coeur.**
#:
#: Ce que la tolerance couvre, et rien de plus : le module `execution.py`, pour
#: le seul nom `subprocess`. Les sept autres lanceurs y restent interdits, et
#: `subprocess` reste interdit dans les vingt autres modules du paquet. Les
#: quatre tests qui suivent la bornent : un site d'appel unique, un argv qui
#: est un chemin de dossier, aucun interpreteur ni commande du depot, et une
#: phrase au lieu d'une exception quand aucun bureau ne repond.
LANCEURS_TOLERES: dict[str, tuple[str, ...]] = {
    "execution.py": ("subprocess",),
}

#: Les trois seuls ouvreurs de bureau que la tolerance autorise. Aucun n'est un
#: interpreteur, aucun n'est une commande de ce depot -- c'est la moitie de la
#: forme qu'`EPIC11-ARB-85` impose, et elle se mesure sur les VALEURS de la
#: table du module, pas sur une relecture de son texte.
OUVREURS_DE_BUREAU = {"open", "explorer", "xdg-open"}

#: Fichiers du coeur qu'on accepte de voir bouger depuis le `baseline_commit`.
#: Une story qui a une raison d'en toucher un s'inscrit ici AVEC son motif --
#: c'est la forme « tolerance documentee » de la politique de revue, et non un
#: affaiblissement silencieux de la garde.
#:
#: **La garde a mordu pour de vrai le 2026-08-28**, et pas sur une story de
#: l'Epic 11 : le commit `e14b783`, d'un agent voisin travaillant sur
#: l'empaquetage, a retire de `cli.py` les sous-commandes `extract-frames` et
#: `apply-calibration`. L'entree ci-dessous est la trace de ce constat, pas une
#: approbation retroactive -- c'est exactement l'usage prevu.
#:
#: **Le changement ne casse aucun parcours CLI** (`EPIC11-ARB-1`), et c'est
#: mesure : les deux handlers retires etaient des `print("[TODO] ...")` du
#: squelette initial. Aucune des deux commandes n'a jamais rien fait.
#:
#: **Ce qu'il coute en revanche est reel et vit dans `deferred-work.md`** :
#: `apply-calibration` figure au tableau des 13 feuilles CLI d'`EPIC11-ARB-18`
#: et dans une AC de la story 11.6. Le denominateur du perimetre etait donc
#: faux d'une unite, et cette AC portait sur un stub.
#: La source de ce module, relue par `ast` pour mesurer le LITTERAL de
#: `CHANGEMENTS_ACCEPTES` plutot que le dictionnaire construit -- seul le
#: premier porte encore les cles dupliquees.
SOURCE_DU_REGISTRE = Path(__file__).resolve()

CHANGEMENTS_ACCEPTES: dict[str, str] = {
    "src/mixed_media_utility/makepdf.py":
        "Story 11.7, lot B (taches B2, B3, B5) : FICHIER NEUF, et c'est un "
        "DEPLACEMENT, pas une ecriture. Le corps de `cli.makepdf_command` et "
        "celui de `cli.makepdf_calibration_page_command` -- gardes, "
        "resolution du `lot_id`, conformite du lot, rang de tirage, "
        "composition, detection de conflit, journal de compression, rendu, "
        "declaration au manifest -- vivent desormais ici, et les deux "
        "commandes en sont des enveloppes. "
        "MOTIF MESURE (fiche 11.7, « Ce qui n'existe pas », point 1) : la TUI "
        "a interdiction d'importer `cli` (frontiere de la 11.4b, mesuree par "
        "`tests/unit/tui/test_frontiere_cli.py`), et l'atelier Pdf n'avait "
        "donc RIEN a appeler -- `makepdf_command` portait la sequence entiere "
        "dans son propre corps, prenait un objet `args` argparse, imprimait "
        "sur `stderr` et rendait un entier. C'est mot pour mot le motif "
        "d'`EPIC11-ARB-129` pour le temps 2 du Scan, et le troisieme geste de "
        "cette famille apres `scan_detect.run_scan_detect` (7.3) et "
        "`scan_write.ecrire_le_lot_detecte` (11.4b, lot S1). "
        "SANS EFFET OBSERVABLE, et c'est MESURE et non affirme : le dossier "
        "d'identite du lot B1 (`tests/unit/test_makepdf_noyau.py`, references "
        "`tests/fixtures/identite-makepdf-950370eb.json`) rejoue 37 "
        "invocations reelles de `cli.main` -- les onze refus de `makepdf`, "
        "les dix scenarios de la mire, la sequence d'ecriture d'un meme lot "
        "-- et compare code de sortie, `stdout`/`stderr` au caractere pres, "
        "condensats des artefacts, chaque JSON aplati et `logs/makepdf.log`. "
        "L'ensemble des scenarios qui divergent d'un releve joue AVANT le "
        "deplacement est VIDE. Les seuls ecarts sont que l'objet `args` "
        "devient des parametres nommes, que les `print(..., file=sys.stderr)` "
        "deviennent des `raise` nommes (`RefusDeMakepdf` et ses deux "
        "sous-classes) et que le code de sortie devient un `PlanchesDuLot` ou "
        "une `PageDeCalibration`. "
        "DEUX FONCTIONS ET UNE CONSTANTE DE `cli.py` L'ONT SUIVI, parce que "
        "leurs seuls appelants etaient ce corps : "
        "`_apply_default_target_colorspace` et sa constante "
        "`DEFAULT_TARGET_COLORSPACE` (les laisser dans `cli` aurait oblige la "
        "TUI a l'importer pour obtenir le meme defaut), et "
        "`_lot_designation_error`, qui prend desormais trois valeurs nommees "
        "au lieu d'un objet `args`. `_configure_makepdf_logger` n'est plus "
        "qu'un relais vers `makepdf.ouvrir_le_journal` : une interface doit "
        "obtenir LE MEME journal sans importer `cli`.",
    "src/mixed_media_utility/encode.py":
        "Story 11.8, lots B0 et B0 bis (`EPIC11-ARB-143`) : ADDITIF, aucun "
        "corps deplace. Le versionnage des masters etait ECRIT EN ENTIER et "
        "CABLE NULLE PART -- mesure du 2026-09-02 : zero site d'appel en "
        "production pour `resolve_master_version_rank`, pour "
        "`masters_version_watermark` et pour `cle_de_famille_de_master`, et "
        "`build_master_output_path` ne passait jamais `version_rank` a la "
        "fabrique de nom, qui l'acceptait pourtant. "
        "MOTIF MESURE, et c'est le pire mode de panne d'`EPIC11-ARB-89` : "
        "`check_output_destination` refusait un master present en "
        "conseillant, verbatim, « relancer avec --nouvelle-version », et "
        "cette option n'existait a aucun parser. Un operateur qui suivait le "
        "conseil recevait `unrecognized arguments` -- un blocage sec "
        "deguise, dont la seule autre issue etait la destruction. "
        "CE QUI CHANGE : `plan_encode` gagne le mot-cle `nouvelle_version` "
        "(defaut `False`, donc tout appelant existant est inchange) et le "
        "refus nomme de son exclusion avec `overwrite` ; `EncodePlan` gagne "
        "`master_version_rank` et la propriete `masters_family_key` ; "
        "`build_master_output_path` gagne un parametre optionnel "
        "`version_rank` ; le vocabulaire ferme gagne "
        "`VERSION_ET_ECRASEMENT_COMBINES`, pose ici ET dans son miroir "
        "`encode_previz` dans le meme diff ; et `reserve_master_path` offre "
        "une seconde issue NON destructive (AC 4.7). "
        "SANS EFFET SUR LE CHEMIN EXISTANT : sans `--nouvelle-version`, le "
        "rang reste `None`, le nom est celui d'avant, et la seule difference "
        "observable au manifeste est la ligne d'eau posee a la consommation "
        "(AC 4.3), qui etait jusqu'ici ecrite par le seul chemin de "
        "SUPPRESSION -- l'inverse exact du geste que `CLAUDE.md` exige. "
        "\n\n"
        "Story 11.8, lot B2 (AC 3.1 a 3.5), MEME FICHIER, AUTRE LOT : AJOUT "
        "PUR de `list_encodable_lots` et de son porteur `EncodableLot`. Le "
        "coeur savait ADMETTRE un lot (`check_lot_admission`), il ne savait "
        "pas LISTER ceux qui le sont -- et faute de cette fonction, "
        "`tui/projet_lecture.py` en jugeait lui-meme sur une table d'etats a "
        "lui, `ETATS_RECONSTRUITS`, que ce lot retire. "
        "MOTIF MESURE, et l'ecart jouait dans les DEUX SENS a la fois. Sur "
        "la meme fabrique de trois lots, au commit `bad2f294` : un lot a "
        "l'etat `scan` portant ses frames est admis par le coeur et l'entree "
        "`Exports` se fermait dessus (« trop strict ») ; un lot recree depuis "
        "des payloads porte l'etat `reconstruction` SANS `output_frames_dir`, "
        "l'entree s'ouvrait dessus et le coeur le refusait par "
        "`ENCODE_OUTPUT_DIR_NOT_DECLARED` (« trop laxiste »). C'est le motif "
        "d'existence de `check_lot_admission`, ecrit dans sa propre "
        "docstring. "
        "AUCUNE SIGNATURE EXISTANTE N'EST TOUCHEE, et la propriete qui compte "
        "est plus forte qu'un ajout : la fonction neuve APPELLE la garde et "
        "ne recopie pas son critere -- une frontiere negative a l'AST le "
        "mesure sur son source (`tests/unit/test_lots_encodables.py`), parce "
        "qu'une seconde redaction qui dirait la meme chose le jour ou elle "
        "est ecrite ne se voit par aucun test de comportement. Meme motif "
        "qu'`EPIC11-ARB-30` : la TUI n'ecrit aucun jugement metier que le "
        "coeur ne porte pas."
        "\n\n"
        "Story 6.8 (`EPIC11-ARB-190`), MEME FICHIER, AUTRE STORY : ADDITIF, "
        "aucun corps deplace, aucune signature existante cassee. "
        "MOTIF MESURE au 2026-09-03 : le versionnage des frames rescannees "
        "EXISTE (`resolve_output_frames_version_rank`, "
        "`output-frames/<slug>_vN`, `EPIC11-ARB-105`) et l'historique par "
        "lot AUSSI (`lots[].reconstructions`, `EPIC11-ARB-109`) -- mais "
        "`lots[].output_frames_dir` est un champ SCALAIRE reecrit a chaque "
        "passe, et `check_lot_admission` ne lisait que celui-la. Les "
        "versions anterieures etaient donc sur le disque, inscrites a "
        "l'historique, et INATTEIGNABLES a l'export : ecrites pour rien. "
        "CE QUI CHANGE : le module gagne `ReconstructionDeLot`, "
        "`enumerer_les_reconstructions` (ordre du manifest, JAMAIS trie -- "
        "`EPIC11-ARB-109`), un resolveur prive, et le code de refus "
        "`RECONSTRUCTION_INCONNUE` pose ICI ET dans son miroir "
        "`encode_previz` DANS LE MEME DIFF ; `check_lot_admission` et "
        "`plan_encode` gagnent le mot-cle OPTIONNEL `reconstruction_visee` "
        "(rang entier ou dossier relatif POSIX) ; `EncodePlan` gagne "
        "`reconstruction_designee`. "
        "SANS EFFET SUR LE CHEMIN EXISTANT, et c'est la contrainte qui a "
        "forme la story : sans designation, la garde rend le scalaire, les "
        "messages sont ceux d'avant au caractere pres, et `render_summary` "
        "n'emet sa ligne QUE si une passe a ete designee -- le dossier "
        "d'identite d'`encode` fige `stdout` sur 25 invocations reelles. "
        "UNE SEULE GARDE, JAMAIS RECOPIEE : la garde d'ETAT joue dans TOUS "
        "les regimes et avant toute resolution de dossier, ce qu'un banc "
        "mesure sur les trois designations a la fois. "
        "MESURE PAR `tests/unit/test_reconstruction_designee.py`, dont la "
        "fabrique porte TROIS reconstructions avec la cible AU MILIEU et le "
        "scalaire du lot pointant la DERNIERE -- ce qui separe d'un coup un "
        "`find` qui rend le premier, un `break` premature, et un repli "
        "silencieux sur la derniere passe."
        "\n\n"
        "Story 6.7 (Epic 6), lot B, MEME FICHIER, AUTRE STORY : "
        "`execute_plan` gagne le mot-cle `rappel_progression=None` et le "
        "transmet a `codec_profiles.run_encode`. C'est le MAILLON DU MILIEU "
        "d'un canal qui traverse trois signatures -- "
        "`encode_master.encoder_le_master_du_lot` -> `execute_plan` -> "
        "`run_encode` --, et c'est le seul des trois qui ne fait que passer. "
        "AJOUT PUR : aucune signature existante n'est touchee, aucun corps "
        "deplace, et `execute_plan` continue de ne rien ecrire au manifest. "
        "MESURE PAR `tests/unit/test_encode_noyau.py::"
        "test_l_ensemble_EXACT_des_mots_cles_transmis_a_l_EXECUTION`, une "
        "frontiere d'ensemble EXACT qui a signale ce mot-cle de plus comme "
        "elle le devait, et qui a ete retournee AVEC un volet qu'elle n'avait "
        "pas : la valeur transmise est celle de l'appelant, pas un rappel "
        "refabrique en route. Un canal qui perdrait le rappel en chemin "
        "laissait l'egalite d'ensemble verte tout en n'observant plus rien.",
    "src/mixed_media_utility/io/encode_manifest.py":
        "Story 11.8, lot B0 bis (`EPIC11-ARB-143`) : ADDITIF. "
        "`lots[].masters_version_watermark` monte desormais A LA "
        "DECLARATION, calque litteral d'`io.pdf_manifest._declare_sheets` "
        "(`EPIC11-ARB-108` : « il n'y a pas de mecanisme different par "
        "objet »). Le champ etait jusqu'ici declare dans "
        "`project_maintenance` seul, c'est-a-dire chez le module qui le fait "
        "REDESCENDRE : il est rapatrie chez son producteur sous "
        "`MASTERS_WATERMARK_FIELD` et importe de la, plutot que d'ecrire un "
        "second litteral de la meme chaine dans deux modules qui la font "
        "bouger en sens inverse. `ENCODE_LOT_FIELDS` le porte, donc la "
        "frontiere d'egalite d'ensembles le mesure. "
        "`EncodeRecord` gagne `masters_family_key` SANS defaut -- un defaut "
        "vide aurait fait de l'oubli du champ une ecriture silencieusement "
        "sautee, c'est-a-dire la surface morte que cette story repare -- et "
        "`from_command_result` renseigne enfin `EncodedMaster.version_rank`, "
        "declare depuis `EPIC11-ARB-91` et jamais peuple. "
        "AUCUNE FRONTIERE AFFAIBLIE : le verrou statique de la story 5.11 "
        "tient, ce module ne nomme toujours ni la fabrique de nom de master, "
        "ni `get_profile`, ni `build_lot_id` -- la cle de famille est DECIDEE "
        "par `encode.plan_encode` et seulement lue ici.",
    "src/mixed_media_utility/encode_previz.py":
        "APRES LA LIAISON du 2026-09-01. `main` avait ajoute "
        "`RANGS_DE_MASTER_EPUISES` a `encode.ENCODE_REFUSAL_CODES` "
        "(`EPIC11-ARB-89`, versionnage des masters) SANS son miroir litteral "
        "ici, alors que le commentaire de `encode.py` l'exige nommement. "
        "Trois bancs rougissaient, dont celui qui mesure que les deux "
        "vocabulaires COUVRENT le producteur. Le code est repose a la "
        "position exacte du producteur (18) : la confrontation porte sur "
        "l'ORDRE autant que sur les membres. Defaut de `main`, ferme ici."
        "\n\n"
        "Story 6.8 (`EPIC11-ARB-190`) : `RECONSTRUCTION_INCONNUE` ajoute en "
        "queue du miroir, DANS LE MEME DIFF que chez son producteur et a la "
        "MEME POSITION. C'est exactement la discipline que le rattrapage "
        "ci-dessus a du payer apres coup ; une ligne de tuple, aucune "
        "signature touchee, aucun comportement de ce module modifie.",
    "src/mixed_media_utility/encode_master.py":
        "Story 11.8, lot B1 (AC 2.1, 2.2, 2.4) : FICHIER NEUF, et c'est un "
        "DEPLACEMENT, pas une ecriture. Le corps de `cli.encode_command` -- "
        "gardes d'ouverture, validation du manifest, decision, recapitulatif, "
        "consentement, balayage des residus, encodage sous le filet de "
        "`SIGTERM`, verification technique, bascule, declaration au manifest -- "
        "vit desormais ici, et la commande en est une enveloppe. "
        "MOTIF MESURE (fiche 11.8, lot B1) : la TUI a interdiction d'importer "
        "`cli` (frontiere de la 11.4b), et l'atelier Exports n'avait donc RIEN "
        "a appeler. Quatrieme geste de cette famille apres "
        "`scan_detect.run_scan_detect` (7.3), "
        "`scan_write.ecrire_depuis_le_document` (11.4b) et "
        "`makepdf.generer_les_planches_du_lot` (11.7). "
        "POURQUOI UN MODULE NEUF ET PAS `encode.py` : ce dernier declare -- et "
        "`test_the_decision_module_still_never_writes_the_manifest` VERROUILLE "
        "-- qu'il n'ecrit jamais le manifest, en comptant a zero les noms "
        "`persist_encode` et `_atomic_write` dans son source. La sequence "
        "deplacee, elle, declare au manifest depuis la story 6.5. La poser "
        "dans `encode.py` aurait casse une frontiere mesuree pour loger une "
        "commodite ; elle vit a cote, comme `makepdf.py` vit a cote de "
        "`pdf_composition.py`. "
        "SANS EFFET OBSERVABLE, et c'est MESURE et non affirme : le dossier "
        "d'identite du lot (`tests/unit/test_encode_noyau.py`, reference "
        "`tests/fixtures/identite-encode-bad2f294.json`) rejoue 25 invocations "
        "reelles de `cli.main` qui ENCODENT pour de vrai -- 12 masters, quatre "
        "codecs, deux conteneurs, les quatre codes de sortie atteignables -- et "
        "compare code de sortie, `stdout`/`stderr` au caractere pres, condensat "
        "SHA-256 de chaque fichier, rapport `ffprobe` champ a champ, chaque "
        "JSON aplati et `logs/encode.log`. L'ensemble des scenarios qui "
        "divergent d'un releve joue AVANT le deplacement est VIDE. Les seuls "
        "ecarts sont que l'objet `args` devient des parametres nommes, que les "
        "`print` et l'invite `stdin` deviennent trois rappels optionnels, et "
        "que le code de sortie devient un `MasterDuLot`."
        "\n\n"
        "Story 6.8 (`EPIC11-ARB-190`) : le point d'entree gagne le mot-cle "
        "OPTIONNEL `reconstruction_visee`, transporte tel quel a "
        "`plan_encode`, et `MOTS_CLES_DE_LA_DECISION` le gagne DANS LE MEME "
        "DIFF -- la frontiere d'ensemble EXACT rougirait sinon, et c'est "
        "elle qui a attrape le `TypeError` sur tout `mmu encode` a la "
        "couture des lots B0 et B1. "
        "IL ENTRE ICI ET PAS AU PARSER, et c'est mesure : deux scenarios du "
        "dossier d'identite recopient la ligne `usage:` d'argparse, qui "
        "enumere les options -- une option de plus les ferait diverger et "
        "exigerait de rejouer la reference sur `cf0e6f4f`. Le consommateur "
        "vise est l'atelier Exports (11.8, ecran 1), qui appelle ce module "
        "et non `cli`. `cli.py` reste donc HORS du diff de cette story."
        "\n\n"
        "Story 6.7 (Epic 6), lot B, MEME FICHIER, AUTRE STORY : "
        "`encoder_le_master_du_lot` gagne le mot-cle `rappel_progression=None` "
        "et le transmet a `encode.execute_plan`. "
        "LE NOM EST CONTRAINT, il n'est pas choisi : "
        "`tui/atelier_exports_execution.le_coeur_sait_compter` lit "
        "`inspect.signature(encoder_le_master_du_lot).parameters` et y cherche "
        "`NOM_DU_RAPPEL_DE_PROGRESSION`, qui vaut `\"rappel_progression\"`. Un "
        "nom different, ou un mot-cle absorbe par un `**kwargs` -- que "
        "`inspect.signature` ne voit pas --, laisserait la TUI figee sur `{}` "
        "SANS QUE RIEN NE LE SIGNALE. La jonction est silencieuse par "
        "construction, et c'est pour ca qu'un banc la mesure des deux cotes. "
        "CONSEQUENCE MESUREE, et c'est la moitie qui ne coute rien : "
        "`le_coeur_sait_compter()` rend `True` depuis ce lot avec ZERO ligne "
        "changee dans `src/mixed_media_utility/tui/`. "
        "LE MOTIF DES TROIS RAPPELS EXISTANTS DE CE MODULE N'EST PAS COPIE, "
        "deliberement : `annoncer_le_recapitulatif`, `confirmer_l_encodage` et "
        "`annoncer_le_master` sont appeles NUS sous un `if ... is not None`, "
        "sans absorption. `rappel_progression` passe par "
        "`progression.EmetteurProgression`, qui absorbe une defaillance du "
        "rappel et ne la journalise qu'UNE fois (`EPIC7-ARB-79`) -- et dont "
        "l'absorption ne couvre QUE le canal, les exceptions du travail "
        "observe traversant intactes, texte compris.",
    "src/mixed_media_utility/cli.py":
        "APRES LA LIAISON du 2026-09-01 : le `finally: "
        "_close_logger_handlers(logger)` que `main` pose sur toutes les "
        "commandes (`a190fb0`) etait accroche, dans `encode_command`, au seul "
        "bloc d'ENCODAGE. Tout ce qui suivait -- « Master ecrit », la "
        "declaration au manifest, ses constats -- partait dans des handlers "
        "deja fermes, et `logs/encode.log` s'arretait net. Quatre bancs "
        "d'integration le mesuraient. Le `finally` enveloppe desormais le "
        "corps ENTIER, ce qui est aussi ce que `a190fb0` voulait. "
        "HISTORIQUE ANTERIEUR A LA LIAISON, garde comme trace : "
        "commit e14b783 (agent empaquetage, 2026-08-28) : retrait des stubs "
        "`extract-frames` et `apply-calibration`, dont les handlers etaient "
        "des `print(\"[TODO] ...\")`. Aucun parcours CLI reel n'est touche. "
        "Consequence sur le perimetre de l'epic : voir deferred-work.md, "
        "section « Epic 11, vague 2 ». "
        "PUIS story 11.4, lot B3 (`EPIC11-ARB-75`) : `extract_command` ne "
        "porte plus la table exception -> code de sortie, elle la LIT dans "
        "`extraction.CODES_DE_SORTIE`. Motif mesure (fait F4 de la 11.4) : "
        "`cli.py:3488-3535` etait la seule source de verite des codes "
        "0/1/2/3/130, or `tui/palier_projet.py:9-12` interdit a la TUI "
        "d'importer `cli.py` et l'AC 7 exige un code retour identique. "
        "SANS EFFET OBSERVABLE : la table du coeur reproduit l'ordre exact "
        "de la pile d'`except` et la recherche rend la premiere entree qui "
        "correspond, donc le meme code pour la meme panne ; "
        "`KeyboardInterrupt` (BaseException) et le filet `OSError` (message "
        "reformule) restent traites a part, et une exception hors table "
        "REMONTE comme avant au lieu d'etre deguisee en refus metier. Mesure "
        "par `tests/unit/test_codes_de_sortie_extract.py`, qui lance la "
        "commande sur les douze entrees, et par les bancs d'`extract` "
        "existants, non modifies. "
        "PUIS story 11.4b, lot S1 (`EPIC11-ARB-67`) : la moitie AVAL du scan "
        "-- correction designee, recadrage, avertissements page par page, "
        "refus prealable d'`EPIC5-ARB-34`, frames, manifest, trace du profil "
        "-- QUITTE ce fichier pour le module de coeur `scan_write.py`, et "
        "`_ecrire_le_lot_detecte` n'en est plus que l'enveloppeur (lecture "
        "d'`args`, deux invites `Y/N`, messages imprimes, code de sortie). ""PUIS story 11.8, lot B1 (AC 2.1) : meme geste pour `encode_command`, qui "
        "perd 224 lignes et ne garde que la lecture d'`args`, le journal de la "
        "commande, les phrases imprimees et le code de sortie -- la table "
        "exception -> code de sortie etant desormais LUE dans "
        "`encode_master.CODES_DE_SORTIE`, comme celle d'`extract` l'est dans "
        "`extraction.CODES_DE_SORTIE` (`EPIC11-ARB-75`). "
        "`_configure_encode_logger` n'est plus qu'un relais vers "
        "`encode_master.ouvrir_le_journal`, et `_EncodeTerminated` comme "
        "`_terminate_kills_the_encoder` sont des ALIAS du coeur -- deux classes "
        "distinctes feraient qu'un `except` de l'une ne verrait pas l'autre, et "
        "le contrat `143` tomberait d'un cote sur deux. SANS EFFET OBSERVABLE, "
        "mesure par le meme dossier d'identite que `encode_master.py` ci-dessus. "
        "Motif mesure (fait F1 de la 11.4b) : la fonction prenait un objet "
        "`args` argparse, imprimait sur `stderr` et rendait un entier, or "
        "`tui/palier_projet.py:9-12` interdit a la TUI d'appeler `cli.py` et "
        "la 11.6 doit ecrire un lot depuis un ecran. La moitie AMONT avait "
        "deja fait ce voyage en 7.3 (`scan_detect.run_scan_detect`) ; la "
        "symetrie etait rompue depuis. "
        "SANS EFFET OBSERVABLE : le corps est DEPLACE, jamais reecrit (geste "
        "de la story 5.26, qui l'avait deja tire hors de `scan_command`) ; "
        "les seuls ecarts sont que l'objet `args` devient des parametres "
        "nommes, que les quatre `print(..., file=sys.stderr)` deviennent des "
        "`raise` et que le code de sortie devient un `EcritureDuLot`. "
        "`scan` et `scan write` rendent les memes codes, les memes messages "
        "et les memes artefacts, mesure par "
        "`tests/unit/test_scan_write_noyau.py` (frames comparees octet pour "
        "octet et entree de lot comparee champ par champ entre la CLI et le "
        "coeur) et par les bancs de scan existants, dont AUCUN banc de "
        "comportement n'a ete modifie. Les valeurs de `CC_FLAG`, `CC_ON`, "
        "`CC_OFF`, `PROFILE_FLAG` et `SET_DEFAULT_PROFILE_COMMAND` sont "
        "desormais lues dans `scan_write` pour la meme raison que les codes "
        "de sortie d'`extract` ci-dessus ; leur prose de justification est "
        "restee ici, aupres des options qu'elle decrit. "
        "PUIS story 11.4b, lot S3 (AC 4) : DEUX LIGNES. "
        "`_ecrire_le_lot_detecte` gagne un parametre `corrections=None` qu'il "
        "relaie en `corrections_manuelles=` au coeur, et `scan_write_command` "
        "lui passe le document de detection BRUT -- pas l'objet relu par "
        "`scan_previz`, qui ne voit pas cette couche, ce qui est meme la "
        "propriete qui la rend additive (`EPIC7-ARB-95`). Motif mesure (fait "
        "F4 de la 11.4b) : `scan_corrections` n'avait AUCUN appelant de coeur, "
        "donc une correction posee etait ecrite au document puis ignoree -- "
        "l'operatrice voyait un succes et n'obtenait pas ses frames, le risque "
        "R12 a la lettre. "
        "AUCUN PARCOURS CLI EXISTANT NE CHANGE, et c'est structurel et non "
        "constate : la couche `manual_corrections` ne peut etre POSEE par "
        "aucune commande de la CLI -- seule une interface la pose (GUI de "
        "l'Epic 7, TUI de la 11.5) --, et un document qui n'en porte pas rend "
        "`corrections_manuelles` sans effet (le couple `(detection, payloads)` "
        "ressort comme le MEME objet, mesure par identite et non par egalite). "
        "`scan` n'en passe aucune : il ecrit dans la foulee de sa propre "
        "detection, sans document. Mesure par "
        "`tests/unit/test_corrections_consommees.py` (14 tests), dont un "
        "bout-en-bout `scan detect` -> correction posee -> `scan write` qui "
        "compare les douze frames produites a celles d'une passe de "
        "reference, condensat par condensat. "
        "PUIS story 11.4c, lot V2 (AC 9) : la MOITIE SCAN rend un "
        "troisieme code. `_ecrire_le_lot_detecte` LIT l'inventaire "
        "qu'elle vient d'imprimer -- avertissements d'ecriture de 5.6 "
        "puis constats de persistance de 5.7 -- et en tire son code de "
        "sortie ; la phrase de succes cesse de dire « succes » quand le "
        "code est degrade et NOMME les motifs ; `_scanner_le_vrac` agrege "
        "par `_code_agrege_du_vrac`, un refus l'emportant sur un succes "
        "partiel, qui l'emporte sur le succes. Rien n'est recalcule ici : "
        "le verdict est celui du coeur (`scan_write.code_de_sortie_de_l_ecriture`), "
        "et la moitie extract de ce fichier n'est PAS touchee. "
        "MOTIF MESURE (defauts D2 et D3 de la fiche 11.4c) : une source "
        "illisible ecrivait quatre frames de mire sur huit, annoncait "
        "`SYNTHETIC_FRAME_WRITTEN`, `FRAMES_SYNTHETIQUES_PRESENTES` et "
        "`LOT_INCOMPLET`, ecrivait `synthetic_frame_count` et "
        "`reconstruction.status: partial` au manifeste -- et rendait `0`. "
        "La tracabilite etait COMPLETE (fait F7) ; ce qui manquait etait "
        "le pont entre elle et le code retour. Un humain lisait les deux "
        "moities de la phrase, un script lisait un succes. "
        "L'EFFET OBSERVABLE EST BORNE ET MESURE, pas suppose : sur les "
        "42 invocations reelles du dossier d'identite du scan, "
        "l'ensemble des scenarios qui divergent du baseline `289f29d` "
        "est EXACTEMENT {`52_source_ILLISIBLE`}, et sa divergence tient "
        "en DEUX chemins -- `code` (0 -> 4) et `stdout[1]` (le verbe). Ni "
        "frame, ni manifest, ni journal, ni `stderr` "
        "(`tests/unit/test_identite_du_scan.py::test_le_pont_de_l_inventaire_ne_change_QUE_le_code_et_le_VERBE`). "
        "Le scenario `51b` -- ecrasement EXPLICITE d'un lot deja passe a "
        "`pdf`, qui annonce `OUTPUT_FRAME_OVERWRITTEN` -- garde son `0` "
        "et ses octets : c'est l'AC 9.4, l'operateur a demande "
        "l'ecrasement. Banc neuf `tests/unit/test_sortie_partielle_du_scan.py` (21 tests). "
        "PUIS story 11.6, lot B (`EPIC11-ARB-129`) : la moitie HAUTE du temps 2 "
        "QUITTE `cli.py` a son tour, et `scan ... calibrate` avec elle. "
        "Motif mesure (fait 1 de « Ce qui n'existe pas » de la fiche 11.6) : "
        "le temps 2 n'avait AUCUN point d'entree de coeur -- lecture du "
        "document de detection, cinq refus nommes, condensat des octets de "
        "chaque source, annonce de completude, trois adaptateurs et refus a "
        "zero page vivaient dans `scan_write_command`, que la TUI a "
        "interdiction d'importer (`EPIC11-ARB-67`), et `gui/` en portait "
        "deja DEUX redactions. Une troisieme dans `tui/` etait la faute que "
        "`EPIC11-ARB-108` nomme -- un mecanisme, un lieu. "
        "SANS EFFET OBSERVABLE : corps DEPLACE, jamais reecrit (troisieme "
        "fois sur cette chaine apres 5.26 et 11.4b) ; les seuls ecarts sont "
        "que l'objet `args` devient des parametres nommes, que les six "
        "`print(..., file=sys.stderr)` de `_refus_de_scan_write` deviennent "
        "un `raise RefusDuDocumentDeDetection` PORTANT LE MEME MESSAGE MOT "
        "POUR MOT, que le `print` de completude devient un rappel optionnel "
        "cable a `print` par la CLI, et que le code de sortie devient un "
        "`EcritureDuLot`. Mesure : les 36 bancs de comportement de "
        "`tests/unit/test_scan_write_command.py` passent SANS RETOUCHE, plus "
        "10 tests neufs a `tests/unit/test_scan_write_noyau.py` (ensemble "
        "EXACT des huit refus, ordre des gardes d'`EPIC5-ARB-34`, document "
        "intact mesure aux inodes et par temoin, frames comparees octet pour "
        "octet a la CLI). Quatre frontieres AST ont suivi leur sujet et "
        "elles seules -- elles nommaient une fonction dans le corps qu'elle "
        "a quitte --, plus 17 `monkeypatch` de `_fit_lot_correction` "
        "retargetes sur `scan_calibrate`, ou vit desormais le corps qu'ils "
        "substituent. "
        "PUIS story 11.13 (`EPIC11-ARB-199`) : `project_remove_command` PERD "
        "SON CLASSEMENT PAR NATURE. Partent la table `libelles` (« pointeur "
        "Git LFS (non materialise) », « fichier local suivi par git », "
        "« donnees de travail NON suivies »), la boucle d'impression par "
        "nature, et l'avertissement final qui nommait les fichiers "
        "irrecuperables. "
        "CE QUI CHANGE D'OBSERVABLE, et c'est le rendu de la commande : "
        "l'entete est INCHANGE (`Apercu:` / `Supprime: element <cible>, N "
        "fichier(s)`) et les chemins sont desormais imprimes A PLAT, dans "
        "l'ordre ou le coeur les a construits, sans en-tete de nature. Le "
        "cardinal se lit maintenant sur `len(rapport.fichiers_a_supprimer)` "
        "au lieu d'une somme sur les trois seaux. "
        "MOTIF : Egan le 2026-09-03, verbatim -- « le suivi par git n'est pas "
        "un sujet [...] il faut supprimer cette ligne ET cette logique du "
        "coeur », « a retirer au plus vite avant la livraison de l'outil ». "
        "`projects/` n'etant plus versionne, tout fichier tombait dans la "
        "derniere categorie par construction : l'avertissement se declenchait "
        "TOUJOURS alors que sa promesse ecrite etait « il n'apparait que "
        "quand c'est vrai ». Un avertissement qui ne discrimine plus rien "
        "n'avertit plus de rien. "
        "CE QUE LA COMMANDE NE PERD PAS, et c'est `EPIC11-ARB-89` : le mode "
        "apercu par defaut, `--confirmer`, la double confirmation du dernier "
        "lot, les codes de sortie `0` / `1` / `130`, l'enumeration des "
        "dossiers de scan et des annexes absentes. Le retrait porte sur le "
        "classement, JAMAIS sur les issues offertes. "
        "L'HISTOIRE DU `git rm -r` DU 2026-08-27 RESTE ECRITE au docstring de "
        "la commande, comme cote coeur. "
        "MESURE PAR `tests/unit/test_frontiere_git_hors_du_coeur.py` (la "
        "frontiere `IRRECUPERABLES` et son volet de morsure) et par les cinq "
        "bancs de commande de `test_suppression_element_de_projet.py` "
        "(apercu, `--confirmer`, second consentement, deux codes `1`), qui "
        "restent verts."
        "\n\n"
        "2026-09-07, MEME FICHIER, AUTRE LOT -- `project remove "
        "--frames-extraites` : AJOUT PUR, la feuille CLI de la cible neuve du "
        "coeur (voir l'entree `project_maintenance.py`). Une option "
        "`store_true` de plus, son passage au coeur, et UNE branche de plus "
        "dans le bloc du rang. "
        "MOTIF MESURE de cette branche, et ce n'est pas cosmetique : sans "
        "elle, la sortie retombait sur « Le rang N reste CONSOMME: un {objet} "
        "posterieur existe », phrase FAUSSE de bout en bout la ou aucun rang "
        "n'est en jeu -- aucun objet posterieur n'existe, et le rang du lot "
        "n'a pas bouge. Le discriminant est le champ `rang_independant` du "
        "rapport, et il ne pouvait pas etre deduit : un objet en QUEUE qui ne "
        "libere aucun rang presente exactement les memes `tirage_en_queue` et "
        "`rangs_liberables`. "
        "POURQUOI LE MOT DE L'OBJET EST LU ET NON ECRIT : la cinquieme entree "
        "de la boucle des libelles passe par "
        "`project_inventory.libelles_de_nature`, comme les quatre autres "
        "(AC 1.3) -- un litteral « jeu de frames extraites » recopie ici "
        "serait le finding `F2` de la revue 11.14, deux mots pour un objet "
        "dans la meme sortie. "
        "CE QU'IL NE REPARE PAS : l'aide de `--version` continue d'enumerer "
        "les QUATRE cibles fines qui l'acceptent et n'y ajoute pas la "
        "cinquieme -- c'est voulu, elle la REFUSE --, si bien qu'un operateur "
        "qui lit cette aide seule ne sait pas que la cinquieme existe ; il "
        "l'apprend de l'aide de `--frames-extraites`, qui le dit, et du refus "
        "s'il essaie.",
    "src/mixed_media_utility/cadence_previz.py":
        "story 11.4, lot B1 et B2 (`EPIC11-ARB-73` et `EPIC11-ARB-76`) : "
        "DEUX AJOUTS PURS. (1) `DisplayUnavailableError` se construit "
        "desormais avec un `motif` et un `conseil` separes et porte les deux "
        "en attributs ; `str(exception)` reste leur concatenation, inchangee "
        "AU CARACTERE PRES sur les cinq sites de levee. Motif mesure : les "
        "trois refus de `ensure_display_available` nomment `--no-display`, "
        "l'option qu'`EPIC11-ARB-41` interdit d'exposer dans la TUI ; la "
        "rendre verbatim violerait l'interdit, la tronquer cote TUI serait "
        "une seconde redaction qui divergerait. (2) `PrevizSession` gagne le "
        "champ gele `cadence_corroboree`, recopie de la qualification a la "
        "construction. Motif mesure (fait F6 de la 11.4) : sur un conteneur "
        "avare -- Matroska sans duree ni `nb_frames` -- le temps 1 de "
        "l'atelier reussit et le temps 2 refuse ; le champ permet d'avertir "
        "au temps 1. SANS EFFET OBSERVABLE : la previz ne refuse rien de "
        "plus qu'avant (`EPIC11-ARB-76` ecarte nommement le refus au temps "
        "1), le champ a un defaut qui reproduit l'etat anterieur, et le banc "
        "`tests/unit/test_refus_affichage_motif.py` compare les cinq "
        "messages a leur chaine exacte -- il etait vert AVANT le changement. "
        "PUIS story 11.4, lot K2 : la LECTURE EN BOUCLE, qui n'existait pas. "
        "Defaut trouve par Egan en testant le produit a la main le "
        "2026-08-30 : `atelier_extraction.py:795` annonce `L boucle` a "
        "l'operateur alors que ce module ne liait QUE quatre touches (`n`, "
        "`p`, `r`, `q`, plus `Echap`) et ne portait AUCUNE notion de boucle. "
        "Motif mesure, et il est pire qu'un cablage manquant : `l` ne faisait "
        "pas rien. Comme toute touche non liee elle tombait dans la branche "
        "PAR DEFAUT de `play_cadences` -- `n` n'a pas de branche a elle -- et "
        "faisait donc AVANCER d'une cadence. Une ligne d'aide annoncait une "
        "fonction jamais ecrite, et la touche annoncee en faisait une autre. "
        "Le module gagne `KEY_LOOP = ord(\"l\")` (la lettre NUE ; `ord(\"L\")` "
        "n'est PAS liee et garde son comportement d'avant), les deux libelles "
        "`OVERLAY_LOOP_ON` / `OVERLAY_LOOP_OFF`, un champ gele `loop_active` "
        "sur `PresentedFrame` et sur `PassOutcome`, un champ `loop` sur "
        "`OverlayText`, la bascule en vol dans `_play_one_pass`, le rejeu de "
        "la cadence courante dans `play_cadences`, et le temoin dessine par "
        "`CvWindowSink._draw_overlay`. "
        "AUCUN PARCOURS `mmu previz` EXISTANT NE CHANGE, et c'est mesure et "
        "non suppose : la boucle est COUPEE au demarrage et rien d'autre que "
        "`l` ne l'arme, donc toute session `--no-display` -- c'est-a-dire "
        "toute session d'integration continue -- se deroule a l'identique. "
        "Mesure par comparaison de `mmu previz --fps 3 --fps 5 --no-display` "
        "entre `HEAD` et l'arbre du lot, sur le meme rush synthetique : meme "
        "code retour, memes lignes, memes cardinaux, memes verdicts, memes "
        "compteurs de decodage et de cache -- seules divergent les mesures de "
        "retard au dixieme de milliseconde, qui sont des lectures d'horloge "
        "reelle. Et par `tests/unit/test_cadence_previz.py`, ou "
        "`test_la_boucle_est_COUPEE_par_defaut_et_le_parcours_CLI_est_INCHANGE` "
        "compare la sequence d'indices SOURCES des deux regimes de sink a "
        "celle de `select_source_frames`. "
        "LE SEUL ECART DE COMPORTEMENT EST CELUI QU'ON CORRIGE : `l` en fin "
        "de passe n'avance plus d'une cadence, elle arme la boucle. C'est "
        "l'objet du lot, et le banc le mesure a l'envers "
        "(`test_l_avance_PAR_DEFAUT_ne_couvre_plus_la_touche_de_boucle`, avec "
        "son volet symetrique : une touche restee non liee avance toujours). "
        "22 mutants injectes en worktree isole "
        "(`scripts/mutation/campagne_11_4_lot_k2.py`).",
    "src/mixed_media_utility/extraction.py":
        "story 11.4, lot B3 (`EPIC11-ARB-75`) : AJOUT PUR. Le module accueille "
        "les cinq codes de sortie d'`extract` (`CODE_SUCCES`, `CODE_ERREUR`, "
        "`CODE_PREREQUIS_ABSENT`, `CODE_REFUS`, `CODE_INTERRUPTION`), la table "
        "`CODES_DE_SORTIE` et les deux lectures `correspondance_de_sortie` / "
        "`code_de_sortie`. Rien d'existant n'est touche : aucune signature, "
        "aucun message, aucun chemin d'execution -- le module ne s'en sert "
        "pas lui-meme, ce sont ses DEUX appelants (`cli.py` aujourd'hui, la "
        "TUI en lot F) qui les lisent. L'ordre de la table est semantique et "
        "reproduit celui de la pile d'`except` qu'elle remplace, filet "
        "`OSError` en dernier. "
        "PUIS story 11.4c, lot V1 (`EPIC11-ARB-83`) : la TRANSITION D'ETAT DU "
        "LOT VISE remonte a l'etape 1, avant ffmpeg. `run_extraction` gagne "
        "un appel a `validate_extraction_state_transition` (nouvelle fonction "
        "d'`io/extraction_manifest.py`, voir son entree ci-dessous) et le "
        "lecteur prive `_etat_declare_du_lot`, qui lit `lots[].state` par "
        "`io.manifest.load_manifest`. Motif MESURE (`EPIC11-ARB-83`) : "
        "l'effacement du lot precedent et le renommage des TIFF sont a "
        "l'etape 5, et `persist_extraction` -- seul endroit d'ou "
        "`LotStateConflictError` pouvait etre levee -- a l'etape 6 ; un lot "
        "deja passe a `pdf` ou au-dela voyait donc ses frames DETRUITES ET "
        "REMPLACEES avant que la transition ne soit jugee, et la phrase "
        "\u00ab Aucune ecriture n'a eu lieu \u00bb que porte le refus n'etait vraie "
        "QUE DU MANIFESTE. Le defaut est anterieur a l'Epic 11 : il mord "
        "`mmu extract` hors de toute TUI. "
        "`_clear_existing_lot` N'EST PAS DEPLACEE -- l'arbitrage l'interdit "
        "nommement, la revue du 2026-08-05 l'ayant deja poussee vers l'aval "
        "pour la raison de correction opposee ; c'est la TRANSITION qui "
        "remonte, pas l'effacement, et "
        "`tests/unit/test_extraction_etat_en_amont.py::"
        "test_le_site_d_appel_de__clear_existing_lot_est_INCHANGE` mesure "
        "l'ordre des cinq appels dans l'arbre syntaxique de `run_extraction`. "
        "AUCUNE MACHINE A ETATS N'EST REECRITE : le jugement est delegue a "
        "`io.manifest.validate_lot_state_transition`, la MEME fonction que la "
        "persistance et que `tui.refus_d_etat_de_lot`, et un test AST mesure "
        "qu'UNE SEULE fonction des deux modules l'appelle. "
        "CE QUI CHANGE POUR LA CLI, et c'est le seul changement observable : "
        "sur un lot deja passe a `pdf`/`scan`/`reconstruction`/`encode`, "
        "`mmu extract` refuse desormais A L'ETAPE 1 au lieu de l'etape 6. "
        "MEME exception (`LotStateConflictError`), MEME message au caractere "
        "pres (une seule redaction, mesuree par egalite de chaines contre le "
        "message de `build_extraction_manifest`), MEME code de sortie (`1`, "
        "par l'entree `ExtractionPersistenceError` de `CODES_DE_SORTIE`). Ce "
        "qui n'arrive plus : le probe ffprobe, la question de confirmation, "
        "l'appel a ffmpeg, la destruction des frames livrees, et -- quand le "
        "dossier de lot etait vide -- l'ecriture d'un lot complet aussitot "
        "suivie d'un refus. L'ordre des DEUX refus d'entree est preserve : un "
        "lot present sur disque SANS `--overwrite` garde son "
        "`ExtractionInputError` d'avant (AC 9 de la story 3.1), la garde "
        "d'etat etant posee juste apres. "
        "Mesure par `tests/unit/test_extraction_etat_en_amont.py` (38 tests, "
        "dont la mesure d'absence d'ecriture aux INODES, au `st_mtime_ns` et "
        "par un TEMOIN -- un condensat ne peut pas voir ce defaut, la fixture "
        "`testsrc` etant deterministe) et par les bancs d'`extract` "
        "existants, dont AUCUN n'a ete modifie.",
    "src/mixed_media_utility/io/extraction_manifest.py":
        "story 11.4c, lot V1 (`EPIC11-ARB-83`) : EXTRACTION DE FONCTION, sans "
        "aucun changement de comportement. Le corps du refus d'etat de "
        "`build_extraction_manifest` -- le `try/except ValidationError` autour "
        "de `validate_lot_state_transition` et la chaine de "
        "`LotStateConflictError` -- devient la fonction publique "
        "`validate_extraction_state_transition(lot_id, current_state)`, que "
        "`build_extraction_manifest` appelle desormais. Aucune ligne du "
        "message n'est reecrite : elle est DEPLACEE, et le seul ecart est que "
        "`record.lot_id` devient un parametre `lot_id`. "
        "MOTIF : `extraction.run_extraction` doit prononcer LE MEME refus a "
        "son etape 1 (voir l'entree `extraction.py` ci-dessus). Le recopier "
        "aurait pose \u00ab deux emplacements pour le meme fait, [donc] deux "
        "verites \u00bb (`EPIC5-ARB-78`), et le lot V3 -- qui doit ajouter au "
        "message une TROISIEME issue, la nouvelle version -- aurait eu deux "
        "endroits a tenir d'accord. "
        "SANS EFFET OBSERVABLE, et c'est mesure : "
        "`tests/unit/test_extraction_manifest.py` (189 tests, non modifie) "
        "couvre les quatre etats aval sur ce chemin, et "
        "`tests/unit/test_extraction_etat_en_amont.py::"
        "test_le_message_du_refus_EN_AMONT_est_EXACTEMENT_celui_de_la_"
        "persistance` compare caractere pour caractere les chaines rendues "
        "par les deux sites d'appel. Un grep de la phrase distinctive du "
        "message sur tout `src/` rend EXACTEMENT ce fichier.",
    "src/mixed_media_utility/io/naming.py":
        "story 11.4, lot P (`EPIC11-ARB-62`) : AJOUT PUR. `build_lot_id` gagne "
        "le mot-cle optionnel `fps_short_name`, et le module gagne "
        "`valider_nom_court_de_cadence`. Motif mesure (deferred-work.md, "
        "2026-08-30) : `format_fps_short` recoit la cadence en `float`, donc "
        "`25/3` y arrive en `8.333333333333334` et le lot s'appelle "
        "`rush_01_8p333333333333334` -- dix-sept chiffres d'artefact la ou "
        "l'arbitrage exige `rush_01_25s3`. Sur un rush NTSC (`24000/1001`) les "
        "QUATRE cadences remarquables sont touchees, ligne « (toutes) "
        "comprise. "
        "POURQUOI ICI ET PAS AILLEURS : l'autre voie -- faire voyager la "
        "`Fraction` exacte jusqu'a `naming` -- touche `format_fps_short` (22 "
        "appels dans `src/`, 24 dans `tests/`), `build_lot_id` (37 et 140), "
        "`validate_extraction_inputs` et le contrat du manifeste, soit une "
        "soixantaine de points d'appel. Le nom court, lui, est CALCULE la ou la "
        "fraction est encore connue (`tui/cadences.nom_court_de_cadence`) et "
        "seul son NOM voyage : zero appelant existant n'est touche. "
        "SANS EFFET OBSERVABLE, et c'est mesure et non suppose : le parametre "
        "a un defaut `None` qui reprend le chemin d'avant AU CARACTERE PRES -- "
        "`tests/unit/test_naming.py::"
        "test_sans_nom_court_le_lot_id_est_EXACTEMENT_celui_d_avant` compare "
        "sept cadences des trois familles a une table de noms ECRITE EN DUR "
        "(et non a `format_fps_short`, qu'un mutant casserait des deux cotes "
        "de l'egalite), dont l'artefact a dix-sept chiffres, qui reste tel "
        "quel sur ce chemin. Le raccourcissement silencieux du chemin "
        "ordinaire est preserve et mesure lui aussi "
        "(`test_le_chemin_ORDINAIRE_garde_son_raccourcissement_silencieux`) : "
        "le durcir changerait le nom d'extractions deja livrees. "
        "DEUX GARDES AJOUTEES, toutes deux sur le seul chemin du nom court : "
        "un nom non conforme a `_MANIFEST_ID_PATTERN` est refuse A L'ENTREE "
        "(sans quoi `validate_manifest` echouerait apres une extraction "
        "longue, motif pour lequel ce pattern vit deja ici), et un depassement "
        "de `CANONICAL_ID_MAX_LENGTH` est REFUSE NOMMEMENT plutot que tronque "
        "par `derive_short_id` -- une troncature remplacerait `25s3` par un "
        "condensat au moment precis ou il etait cense dire « une image sur "
        "trois ». Meme doctrine que le refus de la story 3.7 pour les "
        "extractions bornees, cinq lignes plus haut, et meme arbitrage "
        "d'Egan : l'operateur apprend le probleme quand il peut encore "
        "renommer son fichier. "
        "RACCORD DE `build_extracted_frame_filename` POSE (fin du lot P, "
        "2026-08-30) : la fonction gagne le MEME mot-cle optionnel "
        "`fps_short_name`, de meme forme, meme garde et meme defaut `None`, "
        "et son jumeau `project_layout.rush_dir_slug` aussi (voir l'entree de "
        "ce fichier ci-dessous). MOTIF : `ARB-3` interdit verbatim que « le nom "
        "de dossier de lot et l'identifiant de lot [...] divergent », et un "
        "mot-cle offert a `build_lot_id` seul aurait cree cette divergence au "
        "premier producteur -- c'est le finding `F12` / `Q5` de la story "
        "11.4c, qui le renvoyait nommement « au lot qui livre le producteur ». "
        "L'invariant est mesure sur les DEUX CHAINES PRODUITES, jamais sur le "
        "fait que les deux fonctions appellent la meme brique -- un cablage "
        "identique peut produire deux noms differents : "
        "`tests/unit/test_raccords_du_nommage_des_cadences.py`, sur trois "
        "cadences dont la CIBLE a developpement infini AU MILIEU, plus les "
        "quatre remarquables d'un rush NTSC, en regime borne et non borne. "
        "TOUJOURS AUCUN EFFET OBSERVABLE, et c'est mesure en EGALITE "
        "D'ENSEMBLES sur 1464 cadences (`test_l_ensemble_des_cadences_dont_le_"
        "nom_CHANGE_est_EXACTEMENT_celles_a_developpement_infini`) : "
        "l'ensemble des cadences dont le nom change est EXACTEMENT celles a "
        "developpement decimal infini -- une assertion positive « celles-ci "
        "changent » aurait laisse passer toute divergence supplementaire. "
        "Aucun lot deja livre ne change donc de nom. "
        "RACCORD DE L\u0027ECRITURE NON POSE, et c'est mesure et non prudentiel : "
        "`extraction.run_extraction` derive le nom de lot lui-meme et n'a "
        "aucun argument de nom de lot ; lui passer le nom court cote apercu "
        "ferait annoncer `rush_01_25s3` a l'ecran et ecrire "
        "`rush_01_8p333333333333334` sur le disque, ce qui casserait "
        "`EPIC11-ARB-46` (« l'apercu ne peut jamais mentir »), rendrait "
        "aveugle la garde `refus_d_etat_de_lot` (AC 7.5, load-bearing devant "
        "`EPIC11-ARB-83`) et ferait refuser le lot pour cause de dossier "
        "absent. Le tripwire qui ouvrira le raccord est nomme : "
        "`test_le_raccord_de_L_ECRITURE_reste_ferme_tant_que_le_COEUR_ignore_"
        "le_nom_court` devient rouge le jour ou `run_extraction` gagne le "
        "mot-cle. Voir `deferred-work.md` et la fiche 11.4, lot P. "
        "PUIS story 11.7, lot B0 (2026-09-02, `EPIC11-ARB-171` et "
        "`EPIC11-ARB-175`) : LE NOM D'UN TIRAGE PORTE SA MISE EN PAGE. "
        "`build_sheets_pdf_filename` rend `<projet>_<lot>_<Nf-ori>[_vN].pdf` a "
        "la place de `<projet>_<lot>_planches[_vN].pdf` et gagne un "
        "`template_id` NOMME et obligatoire ; le fragment est DERIVE du "
        "gabarit par `sheets_layout_fragment`, qui lit `page_templates` plutot "
        "que de redecouper la chaine -- la grammaire des `template_id` "
        "appartient a `page_templates`, pas a ce module. Deux symboles neufs "
        "l'accompagnent : `LEGACY_SHEETS_MARKER` et "
        "`legacy_sheets_pdf_filename`, l'ANCIENNE forme RECONNUE et plus "
        "jamais ecrite. "
        "MOTIF MESURE (retour A4 d'Egan sur la planche v5) : le mot `planches` "
        "ne portait aucune information -- tout ce dossier est des planches -- "
        "pendant que deux mises en page du MEME lot rendaient le MEME NOM, ce "
        "qui rendait le motif du conflit opaque (« ce tirage existe deja », "
        "sans dire que c'est une autre forme). Le nom n'a pas grandi, et le "
        "chiffre de la mesure vit dans la docstring de "
        "`build_sheets_pdf_filename` plutot qu'ici -- il n'y a qu'un seul "
        "endroit ou une valeur mesuree s'ecrit. "
        "CHANGEMENT DE COMPORTEMENT ASSUME, et il est double : (1) les "
        "tirages ECRITS A PARTIR DE MAINTENANT changent de nom ; (2) aucun "
        "fichier deja ecrit n'est renomme (portee tranchee par Egan sur "
        "`EPIC7-ARB-91`), et c'est exactement pourquoi "
        "`legacy_sheets_pdf_filename` existe -- un tirage deja pose sur un "
        "disque a CONSOMME SON RANG, et l'ignorer ferait re-attribuer ce rang "
        "a une planche neuve, donc deux feuilles PAPIER portant le meme "
        "« tirage N », ce qu'`EPIC11-ARB-92` interdit et qu'aucun fichier ne "
        "rattrape une fois l'encre seche. "
        "AUCUNE GARDE DE LONGUEUR N'EST POSEE ICI (AC 2.9e) et c'est "
        "delibere : la fonction n'en avait aucune, `CANONICAL_ID_MAX_LENGTH` "
        "ne l'a jamais bornee, et en poser une serait un arbitrage neuf que "
        "personne n'a demande. La borne reelle est celle du systeme de "
        "fichiers, que ce module ne connait pas ; routee en dette. "
        "MESURE PAR les trois bancs neufs du lot -- "
        "`tests/unit/test_nommage_des_tirages.py`, "
        "`tests/unit/test_enumeration_des_tirages.py`, "
        "`tests/unit/test_rang_de_tirage_decouple.py` --, dont une frontiere "
        "negative sur la collision de deux orientations qui partageraient "
        "leurs `ORIENTATION_ABBREV_LENGTH` premieres lettres. Commits "
        "`55254fdc` et `04ec6f5d`."
        "\n\n"
        "Story 6.8 (`EPIC11-ARB-190`), MEME FICHIER, AUTRE STORY : AJOUT PUR "
        "de `rang_du_fragment_de_version`, l'INVERSE de "
        "`format_version_suffix`, pose juste a cote d'elle. Aucune signature "
        "existante n'est touchee. "
        "MOTIF : la story 6.8 doit lire le rang qu'un dossier "
        "`output-frames/<slug>_vN` porte, et il n'existait AUCUNE lecture de "
        "ce fragment dans `io/naming` -- seulement sa fabrique. La seule "
        "autre lecture du depot vit dans `scan_ingest`, pour un role "
        "DIFFERENT (elle RESERVE le fragment dans un slug d'ingestion, afin "
        "qu'un dossier ne soit pas a la fois un scan a part entiere et la "
        "version d'un autre). Ecrire une troisieme expression reguliere dans "
        "`encode.py` aurait fait de la forme `_v<rang>` une convention a "
        "trois proprietaires ; une frontiere du banc neuf compte a ZERO les "
        "expressions sur ce fragment dans le source d'`encode.py`. "
        "MESURE PAR `tests/unit/test_reconstruction_designee.py` : l'aller-"
        "retour sur TOUTE la plage des rangs (2 a 99), et le volet negatif "
        "-- `_v1` (jamais ecrit), `_v0`, `_v100`, `_v02` (`EPIC11-ARB-88` "
        "refuse le zero de tete) et `_v2` sans tige rendent tous l'ORIGINE. "
        "Le refactor de `scan_ingest` n'est PAS fait ici : il appartient a "
        "la story qui touchera ce module.",
    "src/mixed_media_utility/io/project_layout.py":
        "story 11.4, fin du lot P (`EPIC11-ARB-62`) : AJOUT PUR. "
        "`rush_dir_slug` gagne le mot-cle optionnel `fps_short_name`, et "
        "`frames_dir` / `output_frames_dir` le TRANSMETTENT tel quel -- elles "
        "n'en composent aucun nom, elles assemblent un chemin. "
        "MOTIF, et c'est le meme fait qu'`ARB-3` : le lot P avait ouvert le "
        "mot-cle dans `naming.build_lot_id` seul, si bien qu'un lot nomme par "
        "la convention `_25s3` aurait porte un nom de DOSSIER issu de "
        "`format_fps_short` -- exactement la divergence qu'ARB-3 interdit, "
        "creee en posant la convention qui existe pour l'eviter. Les deux "
        "moities du lot (`frames/` et `output-frames/`) recoivent le mot-cle "
        "ensemble : un mot-cle offert a l'une seule leur ferait porter deux "
        "noms, et l'`encode` chercherait les frames rescannees sous un dossier "
        "inexistant. "
        "UNE GARDE, et elle n'est pas decorative : le nom court passe par "
        "`naming.valider_nom_court_de_cadence`, parce que le slug devient un "
        "COMPOSANT DE CHEMIN -- `25/3` ou `../x` ecrirait le lot hors de "
        "`frames/`. C'est le motif deja paye a la revue du 2026-08-08 sur "
        "`scan_output_frames.derive_lot_dir_slug`, ou un TIFF 16 bits avait "
        "ete ecrit hors du dossier projet. Six noms fautifs le mesurent, avec "
        "leur volet symetrique sur cinq noms canoniques. "
        "SANS EFFET OBSERVABLE : defaut `None`, chemin d'avant repris au "
        "caractere pres, mesure contre une table de fragments ECRITE EN DUR "
        "(jamais contre `format_fps_short`, qu'un mutant casserait des deux "
        "cotes de l'egalite) dans "
        "`tests/unit/test_raccords_du_nommage_des_cadences.py::"
        "test_sans_le_mot_cle_les_TROIS_chemins_rendent_EXACTEMENT_les_noms_"
        "d_avant`. Aucun appelant existant de `src/` ne passe le mot-cle.",
    "src/mixed_media_utility/codec_profiles.py":
        "commit 243bebb (2026-08-29) : ajout de `frame_index_to_timecode`, la "
        "reciproque de `timecode_to_frame_index` qui manquait. Elle est la "
        "dependance de `scan_corrections._slots_interpoles` ci-dessous : sans "
        "elle, toute planche a deux frames ou plus levait un `AttributeError`. "
        "AJOUT PUR -- aucune signature existante n'est touchee, et le banc "
        "`tests/unit/test_frame_index_to_timecode.py` (54 cas) mesure la "
        "reciprocite dans les deux sens."
        "\n\n"
        "Story 6.7 (Epic 6), lots A et C, MEME FICHIER, AUTRE STORY : le "
        "CANAL DE PROGRESSION de l'encodage. `ensure_uniform_frame_shapes` et "
        "`run_encode` gagnent le mot-cle `rappel_progression=None`, et "
        "`build_encode_command` le mot-cle `progress_target=None` ; une "
        "couture neuve `_executer_ffmpeg_en_comptant` porte les deux branches "
        "d'execution que `run_encode` portait lui-meme. "
        "MOTIF MESURE, et il vient d'`EPIC11-ARB-184` : l'atelier Exports de "
        "la story 11.8 se livre au ROTOR parce que `run_encode` faisait un "
        "seul `subprocess.run` bloquant et que `build_encode_command` ne "
        "portait aucun `-progress` -- mesure que "
        "`test_atelier_exports_execution.py` refaisait SUR LE PRODUIT, et non "
        "sur une fiche. Le coeur ne savait donc pas compter, et l'ecran ne "
        "pouvait pas afficher un compte qui n'existe pas. "
        "CE QUI CHANGE : trois signatures gagnent un mot-cle optionnel a "
        "defaut `None` -- jamais un parametre existant renomme -- et l'argv "
        "gagne `-progress pipe:1` en option GLOBALE a l'index 2, apres le "
        "`-n`/`-y`. Les quatre contraintes de position deja mesurees "
        "(`command[:2]`, la tranche `concat -safe 0` collee a `-i`, les deux "
        "`-r` egaux, `-f <muxer>` avant le chemin) restent vraies. "
        "SANS EFFET SUR LE CHEMIN EXISTANT, et c'est mesure par egalite de "
        "LISTES : sans rappel actif, `build_encode_command` rend un argv "
        "EGAL a celui d'avant la story -- l'option n'apparait que si "
        "quelqu'un ecoute --, et la couture reprend exactement "
        "`subprocess.run(command, capture_output=True, encoding=\"utf-8\", "
        "errors=\"replace\")`. C'est le repli `AR3`, et il n'acquiert aucune "
        "dependance neuve, en particulier pas au repertoire temporaire "
        "systeme. "
        "CE QUE LA STORY NE FAIT PAS, et il faut le lire : l'ecran ne compte "
        "toujours PAS. Rendre une barre demanderait de modifier `tui/`, ce "
        "que l'AC de frontiere de la 6.7 interdit et ce que l'AC 9.2 de la "
        "story 11.8, livree, ferait rougir. Le rotor reste. Ce qui a bascule "
        "est la POSSIBILITE, et c'est le terrain qu'`EPIC11-ARB-184` avait "
        "prepare des deux cotes.",
    "src/mixed_media_utility/scan_write.py":
        "story 11.4b, lot S1 (`EPIC11-ARB-67`) : FICHIER NEUF. Il porte le "
        "corps DEPLACE de `cli._ecrire_le_lot_detecte` -- rien d'autre --, "
        "avec la signature d'un producteur de coeur : parametres nommes, "
        "aucun objet `args`, aucun `print`, aucun code de sortie ; il LEVE "
        "les exceptions du coeur et rend un `EcritureDuLot`. C'est le "
        "symetrique aval de `scan_detect.run_scan_detect` (story 7.3), qui "
        "existait pour exactement ce motif. Il ne lit JAMAIS `stdin` : les "
        "deux decisions qui se posaient a un humain entrent par des "
        "parametres nommes, parce que sous une boucle d'evenements un appel "
        "bloquant sur `stdin` gele l'interface entiere (`EPIC7-ARB-106`, "
        "paye cote GUI avec `QMessageBox.exec()`). Deux frontieres AST le "
        "mesurent (`tests/unit/tui/test_frontiere_cli.py`), chacune avec son "
        "volet symetrique. AUCUN comportement observable de la CLI ne change "
        "(AC 10), et l'ordre d'`EPIC5-ARB-34` -- `check_scan_conflicts` "
        "avant `write_lot_output_frames` avant `persist_scan` -- a voyage "
        "avec le corps et est mesure A L'ARRIVEE, a l'execution comme au "
        "source. "
        "PUIS story 11.4b, lot S3 (AC 4) : il CONSOMME la couche "
        "`manual_corrections`. Ajouts : le parametre `corrections_manuelles`, "
        "`consommer_les_corrections_manuelles`, `_modele_de_completion`, et "
        "l'entree `scan_corrections.CorrectionInvalide` de `CODES_DE_SORTIE` "
        "-- sans elle une identite incompletable sortait de `mmu scan write` "
        "en trace Python nue au lieu du `Erreur: <motif>` + code 1 qu'exige "
        "l'AC 4.5. La consommation est le PREMIER geste de la sequence, avant "
        "toute ecriture sur le disque (l'import du profil designe en est deja "
        "une) : meme doctrine que l'ordre d'`EPIC5-ARB-34`, « un refus qui "
        "arrive apres une destruction n'est pas un refus ». Mesure sur le "
        "DISQUE et non sur le seul type d'exception -- inode ET `st_mtime_ns` "
        "de chaque fichier du projet, plus un temoin depose dans le dossier de "
        "lot : les frames sont ecrites par `cv2.imwrite` EN PLACE, donc leur "
        "inode survit a une reecriture complete et une mesure d'inodes seule "
        "serait un faux negatif (mesure de ce lot ; le volet symetrique "
        "verifie que l'empreinte bouge sur une passe qui reecrit vraiment). "
        "SANS EFFET quand rien n'est pose : `corrections_manuelles=None`, un "
        "document sans couche ou une couche annulee rendent le MEME couple "
        "`(detection, payloads)` -- mesure par identite d'objet, pas par "
        "egalite, parce qu'un tuple reconstruit a l'identique passerait une "
        "comparaison par valeur tout en ayant traverse une seconde redaction "
        "de l'appariement page <-> payload. "
        "PUIS story 11.4b, lot S5 (AC 9.1) : UN PARAMETRE, `rappel_progression`, "
        "relaye TEL QUEL a `scan_output_frames.write_lot_output_frames`, qui "
        "l'accepte depuis la story 5.28 et a qui PERSONNE ne le passait -- "
        "zero occurrence du mot dans tout `cli.py` (fait F9 de la 11.4b). "
        "Aucun `EmetteurProgression` n'est construit ici et aucun jalon n'y "
        "est emis : ce module PASSE le canal, il n'en redige pas un second "
        "(AC 9.2). SANS EFFET OBSERVABLE quand il vaut `None`, qui est le "
        "regime de tous les appelants existants -- `AR3`, mesure sur les "
        "artefacts produits : les douze frames sont comparees CONDENSAT PAR "
        "CONDENSAT et l'entree de lot CHAMP PAR CHAMP entre une passe sans "
        "rappel, une passe avec un rappel qui note, une passe avec un rappel "
        "qui LEVE a chaque appel, et une passe avec un objet NON APPELABLE. "
        "Le regime POSITIF est mesure aussi, et c'est lui qui coute : "
        "l'emetteur reellement construit par le coeur est lu ACTIF et porte "
        "`total == 12`. Motif mesure le 2026-08-30, cote extraction, ou le "
        "meme defaut valait un bloquant : "
        "`EmetteurProgression.__init__` fait `rappel if callable(rappel) else "
        "None`, donc un appelant qui transmet un objet non appelable eteint "
        "le canal SANS LEVER ET SANS TRACE -- barre figee a `0/N`. « Aucun "
        "jalon » ne distingue pas « canal mort » de « rien a faire » ; "
        "`actif` et `total`, eux, le disent. "
        "PUIS story 11.4c, lot V2 (AC 9 et AC 10) : DEUX AJOUTS, tous "
        "deux de coeur. (1) LE PONT ENTRE L'INVENTAIRE ET LE CODE DE "
        "SORTIE : `CODE_SUCCES_PARTIEL = 4` (distinct des cinq codes "
        "deja pris, 0/1/2/3/130), `VOCABULAIRE_DE_L_INVENTAIRE` -- les "
        "onze avertissements d'ecriture de 5.6 et les huit constats de "
        "persistance de 5.7, LUS chez leurs producteurs et jamais "
        "recopies --, l'ensemble FERME `MOTIFS_QUI_DEGRADENT_LE_CODE` "
        "= {`LOT_INCOMPLET`, `FRAMES_SYNTHETIQUES_PRESENTES`}, et les "
        "trois lectures pures `inventaire_de_l_ecriture`, "
        "`motifs_de_degradation`, `code_de_sortie_de_l_ecriture`. AUCUN "
        "recalcul : ce module RELAIE l'inventaire que 5.6 et 5.7 "
        "produisent deja, une seconde redaction serait la deuxieme verite "
        "d'`EPIC5-ARB-78`. L'ensemble est mesure en EGALITE D'ENSEMBLES "
        "en jouant le pont sur les DIX-NEUF codes du vocabulaire, un par "
        "un -- une assertion positive laisserait passer un motif ajoute. "
        "(2) LE CONFLIT DE CONTENU : `ConflitDeContenuDuLot`, "
        "`masters_declares_du_lot` et `refuser_le_conflit_de_contenu`, "
        "appele APRES `check_scan_conflicts` -- donc sur une identite de "
        "lot deja validee -- et AVANT `write_lot_output_frames`, donc "
        "avant le premier octet ecrit (ordre d'`EPIC5-ARB-34`). Ecraser "
        "sous `--overwrite` des frames qu'un master video declare avoir "
        "consommees (`lots[].encoded_masters`, story 6.5) est refuse, et "
        "le refus NOMME le lot et TOUS ses masters. "
        "CE REFUS PORTE SUR LE CONTENU, JAMAIS SUR L'ORDRE DES ETATS, et "
        "ce n'est pas une precaution de style : "
        "`io/reconstruction._resolve_lot_state` (`:801-819`) pose "
        "verbatim que « rescanner un lot deja passe en `reconstruction` "
        "ou en `encode` est le scenario nominal » et que « le seul echec "
        "dur reste le conflit de contenu, jamais l'ordre des etats ». Un "
        "test parametre sur ces deux etats, SANS master declare, rougit "
        "sur tout refus fonde sur l'ordre. La lecture du manifeste passe "
        "par le seul point d'entree public (`io.manifest.load_manifest`) "
        "et l'appariement se fait par `lot_id` -- fixture a TROIS lots, "
        "la cible AU MILIEU, le premier portant lui aussi un master "
        "(mutant `M25` de la 5.7). Le « rien n'a ete detruit » se mesure "
        "aux INODES, au `st_mtime_ns` et par un TEMOIN, jamais par "
        "condensat. "
        "SANS EFFET quand rien ne degrade : un lot complet sans mire rend "
        "`0` et le mot « succes », et un lot en etat `encode` sans master "
        "declare se reecrit comme avant -- les deux volets symetriques "
        "sont au banc neuf `tests/unit/test_sortie_partielle_du_scan.py`. "
        "PUIS story 11.6, lot B (`EPIC11-ARB-129`) : la moitie HAUTE du temps 2 "
        "ARRIVE ici, deplacee de `cli.scan_write_command`. Surfaces neuves : "
        "`RefusDuDocumentDeDetection` (message positionnel, `motif` nomme), "
        "`MOTIFS_DE_REFUS_DU_DOCUMENT` (ensemble FERME et ORDONNE de huit "
        "motifs, dans l'ordre des gardes d'`EPIC5-ARB-34`), "
        "`MOTIFS_DE_REFUS_A_LA_LECTURE`, `lire_le_document_de_detection` -> "
        "`DocumentDeDetectionLu`, `verifier_les_condensats_des_sources`, "
        "`annonce_de_completude`, `objets_consommables_du_document`, les "
        "trois adaptateurs `PageDetecteeDuDocument` / `DetectionDuDocument` / "
        "`IngestionDuDocument`, et le point d'entree "
        "`ecrire_depuis_le_document`. `EcritureDuLot` gagne un champ "
        "`rapport` (defaut `None`) : le compte rendu final le lit "
        "(`scans_dir`, `len(pages)`) et l'appelant ne le construit plus. "
        "AJOUTS PURS : aucune signature existante ne change, "
        "`ecrire_le_lot_detecte` est appelee avec les memes valeurs "
        "qu'avant. La table `CODES_DE_SORTIE` gagne une entree au meme "
        "code `1` que les autres refus du coeur -- avant l'extraction, "
        "`cli` les rendait deja tous par `return 1` derriere `Erreur: `.",
    "src/mixed_media_utility/scan_corrections.py":
        "commit 289f29d (2026-08-29) : rapatriement du module depuis "
        "`origin/claude/epic-7`, ou la story GUI 7.5 l'a ecrit. Il porte le "
        "point d'entree de completion manuelle d'un QR muet dont la story 11.5 "
        "depend (`EPIC11-ARB-64`). FICHIER NEUF sur cette branche : il ne "
        "modifie aucun comportement existant, aucun appelant du coeur ne "
        "l'importe encore. Sa consommation a l'ecriture est une AC de la "
        "story 11.4b (`EPIC11-ARB-67`). "
        "PUIS story 11.4b, lot S3 (AC 4) : le module reste INCHANGE par ce "
        "lot-la -- pas une ligne --, mais il a desormais son appelant de "
        "coeur, `scan_write.consommer_les_corrections_manuelles`. La phrase "
        "« aucun appelant du coeur ne l'importe encore » ci-dessus est "
        "donc PERIMEE ; elle est gardee pour l'historique, c'est l'etat qui a "
        "motive l'AC 4. "
        "PUIS story 11.4b, lot S4 (AC 5, `EPIC11-ARB-64`) : AJOUT PUR de "
        "`modele_depuis_le_manifeste` et de sa table de sources "
        "`_SOURCE_AU_MANIFESTE` -- 154 insertions, ZERO suppression, ZERO "
        "ligne modifiee, mesure par `git diff --numstat origin/claude/epic-7` "
        "(AC 5.5 : le reste du fichier est identique au caractere pres a la "
        "branche source). Motif mesure (fait F6 de la 11.4b) : "
        "`payload_depuis_l_identite` exigeait un modele DECODE d'une autre "
        "planche du meme lot pour huit champs neutres, exigence heritee de la "
        "GUI ou le lot peut etre ETRANGER. Sept de ces champs sont au "
        "manifeste et le huitieme, `page_count`, se deduit : une pile d'UNE "
        "SEULE planche muette etait donc incompletable pour la seule raison "
        "qu'elle n'a pas de soeur a lire. Le refus du regime 2 (lot inconnu "
        "du projet) est PRESERVE et nomme. SANS EFFET OBSERVABLE : aucune "
        "fonction existante n'est touchee, aucun appelant n'existe encore. "
        "Mesure par `tests/unit/test_modele_de_completion.py` (41 tests), "
        "dont la confrontation du payload complete a la main au payload que "
        "le VRAI QR de la planche soeur a decode dans "
        "`tests/fixtures/detection-scan-reelle/detect-ok-et-refus.json` : "
        "les deux sont egaux champ pour champ.",
    "src/mixed_media_utility/io/reconstruction.py":
        "story 11.4b, lot S2 (AC 3) : PORTAGE depuis `origin/claude/epic-7`, "
        "commentaires d'origine compris. Les quatre fichiers de coeur de ce "
        "lot etaient IDENTIQUES entre les deux branches avant le portage -- "
        "aucune divergence n'a eu a etre reconciliee, ce qui est la seule "
        "raison pour laquelle un portage est ici sans risque. Surfaces "
        "ajoutees : `CHAMP_ORIGINE_ADOPTEE`, `adopter_les_payloads`, "
        "`origine_adoptee`, le mot-cle `adoption=` de "
        "`_check_manifest_conflicts` et `origines_adoptees=` de "
        "`reconstruct_project_manifest`. AUCUNE GARDE DESARMEE, et c'est "
        "mesure et non suppose : `_check_manifest_conflicts` relache "
        "exactement DEUX conditions -- identite de projet, rush inconnu --, "
        "et seulement sur une adoption DECIDEE ; les deux confrontations de "
        "cadence (`fps_target`, `timecode_base_fps`), `_check_pile_homogene`, "
        "`_check_lot_consistency`, `_check_lot_attachment`, "
        "`_check_printed_identifiers` et `_check_page_count` mordent "
        "toujours sur un lot adopte. Un mutant qui mettait `adoption=True` "
        "par defaut -- la garde du chemin d'ECRITURE desarmee -- a d'abord "
        "SURVECU : `reconstruct_project_manifest` passe toujours le mot-cle, "
        "si bien que le defaut n'etait exerce que par le second appelant, "
        "`scan_manifest.check_scan_conflicts:1855`, qu'aucun banc du lot ne "
        "traversait. Il est tue depuis. Mesure par "
        "`tests/unit/test_adoption_de_planche_etrangere.py` (17 tests, 18 "
        "mutants injectes, 18 tues).",
    "src/mixed_media_utility/scan_detect.py":
        "story 11.4b, lot S2 (AC 3) : PORTAGE depuis `origin/claude/epic-7`. "
        "Surfaces : `run_scan_detect(adopter=)`, "
        "`_adopter_les_planches_etrangeres`, `lots_adoptes_du_projet`. "
        "L'adoption a lieu AVANT le tri, et cet ordre est INSTRUMENTE "
        "(`sequence == [\"adoption\", \"tri\"]`), pas seulement constate a "
        "son resultat : posee apres `check_scan_conflicts`, elle ne serait "
        "jamais atteinte. Un echec d'adoption n'arrete pas la passe (AC 3.6) "
        "-- le mutant `continue` -> `break` a d'abord SURVECU sur une "
        "fabrique a deux lots etrangers dont l'echec etait en second, donc "
        "aussi en DERNIER, ou les deux formes sont indiscernables ; la "
        "fabrique porte desormais TROIS lots et l'echec au MILIEU. Le refus "
        "nomme TOUS les projets etrangers de la pile, pas seulement le "
        "premier, et la fabrique place le second ailleurs qu'en premiere "
        "position. "
        "PUIS story 11.4b, lot S5 (AC 9.2) : UN PARAMETRE, "
        "`rappel_progression`, relaye TEL QUEL a "
        "`scan_detection.detect_pages`. Motif mesure (fait F9) : cote "
        "detection, AUCUN canal n'existait, alors que l'ingestion et la "
        "detection d'une pile de quinze pages sont la partie longue. Aucun "
        "`EmetteurProgression` n'est construit ici -- ce module PASSE le "
        "canal --, et le relais est mesure en AST pour qu'il ne puisse pas "
        "devenir un enrobage. La progression ne couvre QUE la detection et "
        "jamais l'ingestion qui la precede : le contrat de l'emetteur exige "
        "un `total` exact par construction, et le nombre de pages n'est connu "
        "qu'une fois l'ingestion faite -- un total devine sur le nombre de "
        "fichiers designes serait faux des qu'une page est illisible et "
        "sautee, ou des que le lot entre par un PDF. SANS EFFET OBSERVABLE "
        "quand il vaut `None` : les documents de detection sont compares "
        "champ par champ, prives du SEUL champ volatil mesure "
        "(`generated_at_utc`), condensat de detection compris. "
        "PUIS story 11.6, lot B : UNE LIGNE. La valeur de "
        "`SCAN_DETECT_SUBCOMMAND` ('detect') vit ici et `cli.py` la lit, "
        "pour la meme raison que `scan_write.CC_FLAG` (`EPIC11-ARB-75`) : "
        "les refus nommes de la moitie haute du temps 2, deplaces au coeur, "
        "renvoient l'operateur vers cette sous-commande, et le coeur ne "
        "peut pas importer `cli.py`. Recopier la chaine aurait laisse deux "
        "verites au meme moment. SANS EFFET OBSERVABLE : meme valeur, meme "
        "aide de sous-parseur, memes messages.",
    "src/mixed_media_utility/scan_calibrate.py":
        "story 11.6, lot B (`EPIC11-ARB-129`, AC 2.6) : MODULE NEUF, et son "
        "contenu est DEPLACE de `cli.py`, jamais reecrit. Il porte le point "
        "d'entree de coeur de `scan ... calibrate` -- `calibrer_la_chaine` "
        "(ingestion, detection, consignation), `consigner_le_profil_de_chaine` "
        "-> `ProfilDeChaineConsigne`, `derive_chain_id` (dont "
        "`cli._derive_chain_id` n'est plus qu'un ALIAS), "
        "`RefusDeCalibration` + `MOTIFS_DE_REFUS_DE_CALIBRATION` (ensemble "
        "FERME de quatre motifs), `CODES_DE_SORTIE` / `code_de_sortie`, "
        "`SCAN_CALIBRATE_SUBCOMMAND` et l'alias `_fit_lot_correction`. "
        "MOTIF MESURE : `calibrate` etait le dernier geste de la chaine de "
        "scan sans point d'entree de coeur -- `scan_calibrate_command` et "
        "`_consigner_le_profil_de_chaine` portaient toute la sequence avec "
        "des `print`, des `sys.stderr` et des codes de sortie --, alors que "
        "la TUI le sert DEPUIS LE MENU D'ATELIER (`EPIC11-ARB-28`) et a "
        "interdiction d'importer `cli.py` (`EPIC11-ARB-67`). "
        "SANS EFFET OBSERVABLE : memes messages, memes codes de sortie, "
        "memes artefacts ; l'invite de nommage devient un rappel appele "
        "EXACTEMENT au meme point (apres le dernier refus, jamais avant), "
        "et `confirmer_l_ecrasement` reste le predicat d'interactivite et "
        "jamais l'invite nue. L'`OSError` du `write_profile` est RENOMMEE "
        "en `RefusDeCalibration` portant son message d'origine mot pour "
        "mot, pour qu'elle ne se fasse pas reformuler par la garde `AR2` de "
        "la commande appelante. Mesure : 140 tests de "
        "`tests/unit/test_scan_calibrate_command.py`, "
        "`test_bascule_calibration_pile_seule.py` et "
        "`test_profil_nomme_par_l_operateur.py` verts, dont AUCUN banc de "
        "comportement modifie.\n\n"
        "Dette `CALIB-N1`, MEME FICHIER, AUTRE LOT (2026-09-07) : DEUX "
        "LIGNES. `calibrer_la_chaine` passe son `rappel_progression` a "
        "`scan_ingest.ingest_scan_lot` en plus de "
        "`scan_detection.detect_lot_pages`. C'est le MEME objet des deux "
        "cotes, jamais enveloppe : agreger les deux suites de jalons ici "
        "casserait l'assertion d'identite (`is temoin`) de "
        "`test_calibrer_la_chaine_TRANSMET_le_rappel` et l'invariant "
        "`EPIC7-ARB-79` qu'elle mesure. Le recollement des deux phases "
        "appartient donc a l'appelant qui AFFICHE une barre -- la TUI, "
        "par `RelaisDesPhasesDeLaCalibration` --, et la ligne de commande "
        "n'en fait rien. AUCUNE SIGNATURE N'A BOUGE : le parametre "
        "existait deja et son type n'a pas change.",
    "src/mixed_media_utility/scan_sorting.py":
        "story 11.4b, lot S2 (AC 3) : PORTAGE depuis `origin/claude/epic-7`. "
        "Surfaces : `lots_adoptes_du_manifest`, "
        "`trier_les_pages(lots_adoptes=)`. L'origine est gardee sur le lot, "
        "et sa consequence fonctionnelle est mesuree jusqu'aux FRAMES : un "
        "second scan du meme lot atterrit sans nouvelle adoption. "
        "ASYMETRIE HERITEE, NON CORRIGEE ICI et consignee en L15 du document "
        "de liaison : `cli.py` appelle `trier_les_pages` SANS `lots_adoptes` "
        "sur son regime de vrac (`:1515`, `:1536`), exactement comme sur la "
        "branche source. La CLI ne lit donc aucune adoption ; seuls "
        "`run_scan_detect` -- donc la GUI et la future TUI -- en "
        "beneficient. Ce n'est pas une regression introduite ici, et la "
        "combler serait un changement observable de la CLI, qu'AC 10 "
        "interdit a cette story.",
    "src/mixed_media_utility/io/scan_manifest.py":
        "story 11.4b, lot S2 (AC 3.8) : PORTAGE depuis `origin/claude/epic-7`, "
        "18 insertions. `preserver_les_sections_de_tete` est publiee et son "
        "ancien nom reste en ALIAS -- aucun appelant existant ne casse. "
        "Motif : le manifest d'accueil doit etre ENRICHI, jamais reecrit ; "
        "`artifacts`, `color`, `video` et `created` sont \"les mesures que le "
        "scan ne pourra jamais refaire, le rush n'etant pas sur cette "
        "machine\". Le banc pose des valeurs DISTINGUABLES dans les quatre "
        "cles avant l'adoption et les relit apres, plutot que d'asserter "
        "leur seule presence. NON PORTE, sciemment : "
        "`scan_manifest.lot_is_complete` (+37/-2), refactoring "
        "d'`EPIC7-ARB-73` (story 7.6) sans rapport avec l'adoption et hors "
        "des cinq surfaces du fait F3 -- c'est tout l'ecart entre les "
        "419/17 annonces par la fiche et les 386/15 reellement portes. Le "
        "drapeau CLI `reconstruct --adopter` n'est pas porte non plus : ce "
        "serait un changement observable de la CLI (AC 10). Les deux sont "
        "en L14 du document de liaison.",
    "src/mixed_media_utility/scan_detection.py":
        "story 11.4b, lot S5 (AC 9.2) : AJOUT PUR. `detect_pages` gagne "
        "`rappel_progression=None` et emet un jalon PAR PAGE DETECTEE, `total` "
        "valant le nombre de pages ingerees. C'est le canal du depot "
        "(`progression.EmetteurProgression`), le meme que l'ecriture emploie "
        "deja depuis la story 5.28 : AUCUN second mecanisme, aucun appel "
        "direct du rappel, aucun `callable()` refait a la main -- une "
        "frontiere AST le mesure sur les trois modules du scan, avec son volet "
        "symetrique (la construction de l'emetteur DOIT etre presente ici). "
        "Le corps de la boucle passe d'une expression generatrice a une boucle "
        "explicite ; l'ordre d'evaluation et le resultat sont identiques, et "
        "le refus de dpi precede toujours l'ouverture du canal. "
        "SANS EFFET OBSERVABLE quand il vaut `None`, qui est le regime de tous "
        "les appelants existants (`detect_lot_pages`, `cli.py`, la GUI) : "
        "memes pages, meme dpi rendu, memes refus -- mesure par comparaison "
        "des documents de detection champ par champ sur quatre regimes de "
        "rappel, dont un rappel qui LEVE a chaque appel et un objet NON "
        "APPELABLE.",
    "src/mixed_media_utility/color_calibration.py":
        "EPIC11-ARB-262 (tranche par Egan le 2026-09-07, sur son constat de "
        "terrain du 2026-09-06 : « Le scan de la page de calibration apparait "
        "en non declare alors que je l'ai importe au projet ») : AJOUT PUR. "
        "`profile_to_document` gagne un parametre `scan_dir` qui vaut `\"\"` "
        "par defaut, et le champ n'est ecrit au document que s'il porte "
        "quelque chose -- meme patron que `label` et `comment`, deja en place "
        "juste au-dessus. Aucun appelant existant ne change de comportement : "
        "un appelant qui ne transmet rien et un appelant qui transmet `\"\"` "
        "produisent le MEME document, ce qui est mesure. "
        "MOTIF MESURE (dette `LOT-I-1`) : c'est la SEULE declaration d'identite "
        "qui relie une mire a son dossier de scan. Ni `chain_id` -- un "
        "condensat du dpi DECLARE, non recalculable depuis le disque -- ni "
        "`source_page_id` n'en portent la trace, et les trois heuristiques de "
        "ressemblance disponibles ecartent un vrai lot de planches. "
        "POURQUOI DANS LE COEUR ET PAS DANS LA TUI : le document de profil est "
        "ecrit par `scan_calibrate.consigner_le_profil_de_chaine`, que la TUI "
        "n'a pas le droit d'appeler autrement que par le coeur heberge "
        "(`EPIC11-ARB-1`) ; le champ ne peut pas etre pose apres coup sans "
        "reecrire un document que le coeur vient de valider. "
        "CE QU'IL NE REPARE PAS, et l'entree le dit plutot que de le taire : "
        "les projets DEJA calibres gardent leur faux orphelin, le champ "
        "s'ecrivant a la calibration -- mesure par "
        "`test_un_profil_SANS_scan_dir_laisse_le_faux_orphelin_ouvert`.",
    "src/mixed_media_utility/scan_ingest.py":
        "story 11.4b, lot S5 (AC 7, `EPIC11-ARB-38`) : AJOUT PUR. Le module "
        "publie `mesurer_le_dpi(scan_path)`, pendant de `slug_par_defaut` et "
        "de `dossier_de_lot_par_defaut` : elle rend la mesure de dpi SANS RIEN "
        "COPIER, SANS RIEN INGERER et SANS EXIGER DE DPI. Motif mesure (fait "
        "F5 de la 11.4b) : `_measure_pages_dpi` est privee et ses trois "
        "appelants exigent deja un dpi ET ont deja copie les fichiers dans le "
        "projet, si bien que « la valeur mesuree est affichee a cote du champ, "
        "des le depot » etait intenable. Rien d'existant n'est touche : ni "
        "`ingest_scan_lot`, ni une signature, ni un message, ni un chemin "
        "d'execution -- la fonction n'est appelee par aucun code de "
        "production, ce sont les ecrans de la 11.5 qui la liront. "
        "LA MESURE RESTE INFORMATIVE (AC 7.3) : elle est confrontee au DPI "
        "declare, JAMAIS substituee, et une frontiere AST balaie le module "
        "entier pour qu'aucune mesure ne puisse etre affectee a un "
        "consommateur de dpi ni passee a un mot-cle `dpi=` / `declared_dpi=` "
        "-- y compris sur une branche qu'aucun test ne deroule. Les QUATRE "
        "formes d'entree d'`EPIC7-ARB-88` sont acceptees, et ce qui n'est pas "
        "mesurable est refuse NOMMEMENT dans `ScanIngestError`, jamais par un "
        "`TypeError` nu (piege deja paye a `scan_detect.py:250-260`). "
        "ECART ASSUME a la recommandation Q2 de la fiche, a signaler en revue : "
        "un PDF est MESURE et non rendu `None`. La premisse de Q2 (« une "
        "valeur derivee d'une taille de media box ») est fausse dans ce depot, "
        "verifie -- `_measure_pdf_dpi` lit le `horizontal_dpi` des images "
        "EMBARQUEES, et elle existe precisement pour faire voir le cas "
        "qu'`EPIC11-ARB-38` veut montrer avant la saisie. Rendre `None` la ou "
        "l'ingestion ecrira `measured_dpi: 200` dix secondes plus tard, ce "
        "serait deux verites pour un seul fait (`EPIC5-ARB-78`).\n\n"
        "Dette `CALIB-N1`, MEME FICHIER, AUTRE LOT (2026-09-07) : AJOUT "
        "PUR d'un `rappel_progression=None` a `ingest_scan_lot`, et de "
        "l'`emetteur` optionnel que `_ingest_files` et `_ingest_pdf` "
        "portent pour lui. Le canal est celui du depot "
        "(`progression.EmetteurProgression`), aucun second mecanisme. "
        "MOTIF MESURE, retour de terrain d'Egan du 2026-09-06 : « la "
        "barre de progression de la calibration saute de 0 a 100 ». "
        "`scan_calibrate.calibrer_la_chaine` enchaine trois phases et "
        "n'en observait qu'une -- l'ingestion, LA PLUS LONGUE sur un PDF "
        "300 dpi puisqu'elle rasterise, etait la seule des trois a "
        "n'emettre rien. Sur une mire (une page), la barre restait donc "
        "immobile pendant tout le travail, puis affichait `1/1`. "
        "SANS EFFET SUR LE CHEMIN EXISTANT, et c'est MESURE : sans "
        "rappel, l'emetteur n'est pas construit, le cardinal des pages "
        "n'est pas mesure (il coute une ouverture de PDF) et les deux "
        "rapports rendus sont compares document a document "
        "(`tests/unit/test_progression_de_l_ingestion_du_scan.py`, "
        "8 verts).",
    "src/mixed_media_utility/io/profile_designation.py":
        "story 11.4b, lot S5 (AC 8) : AJOUT PUR, plus UN CORPS DEPLACE. "
        "Le module gagne `designated_profiles(project_dir)` -- LA LISTE des "
        "profils designes, symetrique de son ecrivain -- et "
        "`designated_profile_path(project_dir, entry)`. Motif mesure (fait F8 "
        "de la 11.4b) : `DESIGNATED_PROFILES_KEY` n'apparaissait qu'a DEUX "
        "endroits de tout le depot, sa definition et son ecriture. UN "
        "ECRIVAIN, ZERO LECTEUR -- un ecran qui doit proposer un profil parmi "
        "ceux du projet n'avait aucun moyen de les enumerer. "
        "AUCUN REPLI N'EST INTRODUIT, et c'est la propriete que le banc "
        "traque : la liste n'invente rien, ne balaie pas "
        "`versions/calibration/` et ne se rabat pas sur le defaut du projet. "
        "Un test ecrit TROIS profils dans le projet sans en designer aucun et "
        "mesure que la liste reste vide -- c'est le seul test du depot capable "
        "de voir le repli automatique qu'`EPIC5-ARB-83` supprime. Aucun "
        "`chain_id` n'est compare : `_upsert` reste le seul endroit du module "
        "qui le fasse (`EPIC5-ARB-101`). "
        "SANS EFFET OBSERVABLE sur l'existant : `default_profile_entry` et "
        "`default_profile_path` gardent leur contrat au caractere pres, leurs "
        "corps etant DEPLACES vers `_color_section` et "
        "`designated_profile_path` -- deux points uniques, jamais deux "
        "redactions. Une seconde resolution de chemin serait la porte par "
        "laquelle `versions/calibration/<chain_id>.json` reviendrait, "
        "c'est-a-dire l'identite redevenue cle de resolution ; le banc mesure "
        "que le defaut et le registre se resolvent par LA MEME fonction, et "
        "que le chemin recompose depuis l'identite n'existe meme pas.",
    "src/mixed_media_utility/pdf_composition.py":
        "story 11.4b, lot S4 (AC 5.1, `EPIC11-ARB-64`) : la pagination d'un "
        "lot -- `ceil(frames / emplacements)` -- cesse d'etre une expression "
        "posee au milieu de `compose_lot_plan` et devient les deux fonctions "
        "publiques `nombre_de_planches` et `page_count_du_lot`. "
        "Motif mesure : `scan_corrections.modele_depuis_le_manifeste` doit "
        "deduire EXACTEMENT le `page_count` que l'impression a pose pour "
        "completer une planche muette, et la formule etait illisible depuis "
        "le chemin de scan. La recopier la-bas en aurait fait une seconde "
        "redaction : elles coincideraient le jour de leur ecriture et "
        "divergeraient a la premiere evolution de la pagination, SANS "
        "qu'aucune etape n'echoue -- c'est la famille du finding 4.3, deja "
        "payee dans ce depot. "
        "SANS EFFET OBSERVABLE : le corps est DEPLACE, jamais reecrit ; "
        "`compose_lot_plan` appelle desormais la fonction et le bloc de prose "
        "qui documentait le calcul voyage avec lui. Les seuls ajouts sont des "
        "REFUS la ou il n'y avait rien (un gabarit a zero emplacement, un "
        "cardinal negatif, un booleen pris pour un entier), tous sur des "
        "entrees qu'aucun appelant du depot ne produit. Mesure par "
        "`tests/unit/test_modele_de_completion.py` -- qui confronte le "
        "`page_count` du modele a celui que `compose_lot_plan` fait imprimer "
        "sur trois paginations dont une qui NE TOMBE PAS JUSTE (10 frames "
        "pour 4 emplacements) -- et par les 678 tests de "
        "`test_pdf_composition.py` et `test_page_geometry_v2.py`, dont AUCUN "
        "n'a ete modifie. "
        "PUIS story 11.4b, lot L (AC 6, `EPIC11-ARB-87`) : LE PIED TECHNIQUE "
        "IMPRIME CHANGE, et c'est un CHANGEMENT DE COMPORTEMENT assume, pas un "
        "ajout pur. Le pied porte desormais DIX renseignements au lieu de six "
        "-- `tbf`, `tcs`, `gmi` et `pc` s'ajoutent --, trois cles sont "
        "raccourcies (`template=` -> `tid=`, `patchs=` -> `ppi=`, "
        "`schema-payload=` -> `sv=`) et la provenance passe de `Mixed Media "
        "Utility makepdf` a `MMU makepdf`. "
        "SEPT DES HUIT CLES SONT DERIVEES de `io.payload.PAYLOAD_SHORT_KEYS`, "
        "jamais ecrites en propre : le depot porte depuis la story 5.17 un "
        "vocabulaire court pour exactement ces champs, celui du QR. En ecrire "
        "un second pour le papier aurait fait porter a la MEME feuille deux "
        "noms courts pour le meme champ -- une seconde redaction du "
        "vocabulaire, famille du finding 4.3 -- et la frontiere "
        "`test_the_table_is_the_only_place_where_a_short_key_is_written` le "
        "refuse d'ailleurs en clair. Seule `dict=` reste ecrite en propre : le "
        "dictionnaire ArUco n'est pas un champ de charge utile. "
        "MOTIF, tranche par Egan le 2026-08-30 : les huit "
        "`CHAMPS_NEUTRES_DU_LOT` deviennent TOUS relisables sur la planche, "
        "donc une pile totalement denuee de QR se retape a la main. Le papier "
        "en portait deja quatre (`project_id`, `rush_id`, `fps_target`, "
        "`patch_preset_id`) ; les quatre ajoutes sont exactement le "
        "complement, et un banc mesure cette egalite EXACTEMENT plutot qu'en "
        "inclusion. "
        "CE QUI RENDAIT LA CHOSE POSSIBLE, et ce n'est pas ce que la mesure du "
        "lot S4 croyait : dans la colonne bornante de 55,188 mm a 8 pt, les "
        "dix mentions en cles COURTES rendent 6 lignes -- exactement ce que "
        "six mentions occupaient --, la ou les memes dix en cles longues en "
        "rendent 9 et debordent. Les segments de diagnostic absorbables avant "
        "debordement en v2 portrait valent 1 AVANT COMME APRES. "
        "AUCUNE ZONE DE DESSIN N'EST TOUCHEE, et c'est mesure et non declare : "
        "`test_le_pied_technique_ne_peut_deplacer_aucune_zone_de_dessin` "
        "charge le pied jusqu'au refus et compare a chaque cran l'empreinte de "
        "dessin -- marqueurs, zones de frames, pastilles, emprise du QR, "
        "rectangles de zones et de blocs -- a l'octet. La seule issue d'une "
        "combinaison qui ne tient pas reste le REFUS, jamais une police "
        "reduite ni une zone retrecie : la geometrie que le scan deduit des "
        "marqueurs en depend. "
        "LA GEOMETRIE v1 EST EXEMPTEE : elle garde ses six mentions et ses "
        "cles historiques, parce que des planches sont deja imprimees avec "
        "(AC 6.4, verbatim : « cela ne vaut que pour les planches imprimees "
        "APRES ce changement »). Le fichier de reference du `baseline_commit` "
        "n'est PAS regenere et "
        "`test_a_v1_lot_is_byte_for_byte_what_it_was_before_the_story` reste "
        "vert. "
        "CORRECTION DU 2026-09-02 : cette phrase disait « reste vert SANS "
        "AVOIR ETE TOUCHE », et cette moitie-la n'est plus vraie -- "
        "`EPIC11-ARB-171` a fait rougir ce banc et sa declaration a du etre "
        "reecrite (voir la suite de cette entree, et celle de "
        "`io/naming.py`). Ce qui reste vrai, et c'est ce qui portait la "
        "promesse : LE FICHIER DE REFERENCE N'EST TOUJOURS PAS REGENERE, et "
        "la geometrie v1 -- zones, pastilles, blocs, marqueurs, pagination, "
        "`template_id` -- est toujours comparee A L'OCTET. Seul le NOM du "
        "fichier a bouge, et le banc le reconstruit au lieu de le recopier. "
        "TOLERANCE DOCUMENTEE ET BORNEE : une mention `cle=valeur` trop longue "
        "s'imprime tronquee avec marqueur visible -- comportement historique "
        "de `_pack_lines` -- et le plan porte le constat nomme "
        "`PIED_TECHNIQUE_TRONQUE`. L'AC 6.2 interdit la troncature MUETTE ; "
        "celle-ci ne l'est plus. Ce n'est deliberement pas un refus : le depot "
        "compose aujourd'hui des lots dont le `target_colorspace` fait 40 "
        "caracteres, et refuser ferait refuser des planches qui s'impriment, "
        "pour un champ que le QR porte toujours EN ENTIER. "
        "PUIS story 11.7, lot B0 ter (2026-09-02, `EPIC11-ARB-175`) : LE RANG "
        "DE TIRAGE SE COMPTE PAR LOT, jamais par mise en page, et il se "
        "DECOUPLE de `--nouvelle-version`. `_rangs_sur_le_disque` balaie "
        "desormais TOUTES les mises en page du vocabulaire pour un lot donne "
        "-- plus l'ancienne forme, reconnue par "
        "`naming.legacy_sheets_pdf_filename` --, et la ligne d'eau qu'il en "
        "tire vaut pour le lot entier ; et `compose_lot_plan` passe au nom le "
        "`template_id` DEJA resolu par `_resolve_parameters`, jamais un second "
        "calcul, pour que le nom suive le gabarit qui a produit les pages. "
        "MOTIF, verbatim d'Egan : « le calcul du rang de tirage se fait par "
        "lot. On traite les memes images selon les mises en pages, le rushe "
        "reconstitue reste le meme » ; « deux fichiers de mises en page "
        "differentes ne partagent jamais un rang ». Consequence 2 de "
        "l'arbitrage : un refus de nom qui echapperait au balayage ferait "
        "DISPARAITRE les tirages des autres formes, d'ou la traduction en "
        "`NamingError` que `sheets_layout_fragment` pose cote `io/naming.py`. "
        "CHANGEMENT DE COMPORTEMENT ASSUME et borne au TIRAGE : la geometrie "
        "dessinee ne bouge pas d'un micron, seul le rang porte au nom, a "
        "l'en-tete imprime et au payload change. Mesure par "
        "`tests/unit/test_rang_de_tirage_decouple.py` et "
        "`tests/unit/test_enumeration_des_tirages.py` ; les limites du "
        "balayage sont routees en dette (`deferred-work.md`, lots B0).",
    "src/mixed_media_utility/pdf_render.py":
        "Story 11.7, lot B4 (vague 5, 2026-09-02) : le rendu des planches "
        "EMET une progression, ce qu'il ne faisait pas. Motif mesure : "
        "`rappel_progression` vit dans onze modules du depot -- sept de coeur, "
        "quatre surfaces -- et il y en avait ZERO dans `pdf_composition.py`, "
        "ZERO dans `pdf_render.py` et ZERO dans tout `cli.py`. L'atelier PDF "
        "de la 11.7 dessine un ecran d'execution avec barre et journal "
        "(`E5-4`) que le coeur ne pouvait alimenter par aucun chemin : c'est "
        "le proprietaire qui l'a vu, note 10 de la relecture v5 (« cette "
        "progression existe au coeur ? »). "
        "CONTRAT REPRIS, JAMAIS INVENTE : celui d'`ecrire_le_lot_detecte` -- "
        "un jalon par page, `total = plan.page_count`, aucun jalon avant la "
        "premiere page. `plan.page_count` est le compte DU LOT et non de la "
        "passe (`LotComposition`, un lot par invocation de `makepdf`) ; "
        "l'agregation sur la passe reste une affaire de surface "
        "(`EPIC11-ARB-134` point 2). "
        "ADDITIF : le rappel est optionnel, les appelants existants ne le "
        "passent pas et ne changent pas de comportement. `cli.py` n'est PAS "
        "touche -- le cablage se fera quand le corps de `makepdf_command` "
        "descendra au coeur (lots B2/B3/B5). "
        "MESURE PAR `tests/unit/test_makepdf_noyau.py`, 11 bancs ecrits "
        "ROUGE d'abord, dont CINQ frontieres negatives, et une campagne de "
        "6 mutants tous tues. L'une de ces frontieres a ete ajoutee en cours "
        "de route et elle vaut d'etre dite : le mutant que l'AC nomme -- un "
        "jalon emis AVANT la boucle -- SURVIT a toutes les mesures de "
        "contenu, y compris a l'egalite de suite, parce que "
        "`EmetteurProgression` refuse un jalon qui ne progresse pas et "
        "absorbe donc le fautif. Seule la mesure de l'ORDRE le tue. La lecon "
        "est portee en section 6.1 bis de "
        "`politique-revue-et-mutation-testing.md`.",
    "src/mixed_media_utility/page_templates.py":
        "Story 11.7, lot B8 (vague 2, 2026-09-02, `EPIC11-ARB-154` et "
        "`EPIC11-ARB-173`) : AJOUT PUR de la DOMINATION des mises en page -- "
        "`MiseEnPageMesuree`, `surface_de_dessin_mm`, "
        "`mesurer_les_mises_en_page`, `domine`, `BilanDeDomination`, "
        "`dominants_des_mises_en_page`, `bilan_de_domination`. **ZERO "
        "suppression** : aucune ligne existante n'est touchee, ce qui se "
        "remesure par `git diff --numstat` entre `BASELINE` (la constante "
        "ci-dessous) et `HEAD` sur ce seul fichier -- 294 insertions au jour "
        "de cette declaration, et c'est la colonne des suppressions, pas "
        "celle-la, qui porte la propriete. "
        "MOTIF DE L'EMPLACEMENT, et c'est lui qui met ce code au COEUR plutot "
        "que dans `tui/` : `EPIC11-ARB-154` demande que la liste des "
        "combinaisons non dominees soit « calculee par le produit et JAMAIS "
        "RECOPIEE ». Comparer deux geometries est une regle de vocabulaire de "
        "geometrie, au meme titre que le retrait d'un cardinal par "
        "`frames_per_page_vocabulary`, qui vit deja ici ; une seconde "
        "redaction dans un ecran coinciderait le jour ou elle est ecrite et "
        "divergerait a la premiere evolution de la geometrie, SANS QU'AUCUNE "
        "ETAPE N'ECHOUE -- famille de defaut deja payee trois fois par ce "
        "depot. C'est aussi `EPIC11-ARB-108` : un mecanisme, un lieu. "
        "SANS EFFET OBSERVABLE : les sept symboles sont NEUFS, aucune "
        "signature existante ne bouge, aucun gabarit du registre n'est touche, "
        "et aucun code de production ne les appelle encore -- seuls les ecrans "
        "de reglages de la 11.7 les liront. La SEULE dependance neuve est un "
        "import DIFFERE de `pdf_composition.nombre_de_planches` (la pagination "
        "n'est jamais redigee deux fois : c'est elle qui a pagine les planches "
        "deja imprimees), et elle va dans le sens ou la dependance existe "
        "deja -- `pdf_composition` importe ce module, pas l'inverse. "
        "MESURE PAR `tests/unit/test_domination_des_geometries.py` "
        "(35 tests), dont une frontiere AST en ENSEMBLE EXACT des symboles du "
        "module touches, et une fabrique a TROIS mises en page dont la cible "
        "est AU MILIEU -- point 2 bis de la regle des fabriques de "
        "`CLAUDE.md`, pose apres qu'une fabrique a deux elements eut laisse "
        "survivre un `continue` -> `break`. Campagne : 29 mutants injectes, "
        "29 TUES, 0 survivant, plus un TEMOIN NEGATIF qui survit comme prevu "
        "(le libelle d'un refus) -- il est la pour prouver que la campagne "
        "sait rendre un survivant. Injecteur prive au lot "
        "(`scratchpad/B8-prive/`), commit `b958015`.",
    "src/mixed_media_utility/project_maintenance.py":
        "Story 11.7, lot B0 (vague 1, 2026-09-02, `EPIC11-ARB-171`) : DEUX "
        "LIGNES, et c'est une CONSEQUENCE MECANIQUE du changement de nom des "
        "tirages, pas un choix propre a ce module. `_planche_pdf_declaree` "
        "cherchait les PDF d'un lot en reconstruisant leur nom par "
        "`naming.build_sheets_pdf_filename` ; cette fonction ecrit desormais "
        "`<projet>_<lot>_<Nf-ori>[_vN].pdf` et exige un `template_id`, que "
        "cette recherche n'a pas. L'appel passe donc a "
        "`naming.legacy_sheets_pdf_filename` -- l'ANCIENNE forme, RECONNUE et "
        "plus jamais ecrite --, et le commentaire de docstring qui la nommait "
        "suit son sujet. "
        "CE N'EST PAS UN REPLI PAR DEFAUT, c'est une DEDUCTION, et elle est "
        "ecrite au point d'appel : on n'arrive dans cette boucle que si le lot "
        "ne declare AUCUN `sheets_pdfs` -- champ pose par `EPIC11-ARB-90`, "
        "donc ANTERIEUR a `EPIC11-ARB-171`. Un manifeste sans inventaire a "
        "forcement ete ecrit avant l'arbitrage, et ses fichiers portent donc "
        "le marqueur `naming.LEGACY_SHEETS_MARKER`. Balayer EN PLUS les mises "
        "en page rendrait le produit des rangs par les gabarits en chemins "
        "candidats par lot, que `_refuser_l_annexe_partagee` reparcourt lot "
        "par lot : un cout quadratique paye pour un cas qui ne peut pas "
        "exister. La limite est routee en dette plutot que tue en silence "
        "(`deferred-work.md`, entrees des lots B0). "
        "SANS EFFET OBSERVABLE SUR LES TIRAGES DEJA POSES, et c'est la "
        "propriete qui compte : aucun fichier deja ecrit n'est renomme "
        "(portee tranchee par Egan sur `EPIC7-ARB-91`), et un tirage a "
        "l'ancienne forme continue donc d'etre VU par `project remove` et de "
        "CONSOMMER son rang -- ce qu'`EPIC11-ARB-92` exige, et qu'aucun "
        "fichier ne rattrape une fois l'encre seche. "
        "MESURE PAR `tests/unit/test_suppression_element_de_projet.py` et "
        "`tests/unit/test_versions_de_planche.py`, mis d'accord dans le meme "
        "commit, plus les trois bancs neufs des lots B0 "
        "(`test_nommage_des_tirages.py`, `test_enumeration_des_tirages.py`, "
        "`test_rang_de_tirage_decouple.py`) et le dossier d'identite du scan "
        "(`test_identite_du_scan.py`). Commits `55254fdc` et `04ec6f5d`. "
        "HISTORIQUE : ce fichier figurait deja parmi les dix-huit que la "
        "LIAISON du 2026-09-01 a amenes de `main` et que le deplacement de la "
        "ligne de base a remis sous surveillance ; l'entree ci-dessus ne porte "
        "que ce que l'Epic 11 y a ecrit APRES ce deplacement. "
        "PUIS story 11.8, lot B0 bis : UNE LIGNE. `MASTERS_WATERMARK_FIELD` "
        "n'est plus un litteral recopie ici mais un import depuis "
        "`io.encode_manifest`, qui l'ECRIT desormais. Le commentaire de ce "
        "bloc promettait deja des noms « importes plutot que recopies, chacun "
        "appartenant au module qui le RESOUT » ; celui-la ne l'etait pas, et "
        "brancher l'ecriture sans le rapatrier aurait fige deux litteraux de "
        "la meme chaine dans les deux modules qui la font bouger en sens "
        "inverse -- ce module la fait DESCENDRE, son producteur la fait "
        "MONTER. Aucun changement de valeur, aucun de comportement : mesure "
        "par `test_suppression_element_de_projet.py`, non modifie. "
        "PUIS story 11.13 (`EPIC11-ARB-199`) : LE SUIVI PAR GIT SORT DU "
        "COEUR, sur demande directe d'Egan le 2026-09-03 -- « le suivi par "
        "git n'est pas un sujet [...] l'utilitaire n'a pas vocation a traiter "
        "des fichiers au sein de depots git. Il faut supprimer cette ligne ET "
        "cette logique du coeur. » Partent : les trois constantes `NATURE_*` "
        "et leur entree dans `__all__`, `_est_pointeur_lfs`, "
        "`_noms_suivis_par_git` (l'unique `subprocess.run(['git', ...])` du "
        "paquet, et avec lui l'import `subprocess`), "
        "`_LFS_POINTER_SIGNATURE` / `_LFS_POINTER_MAX_READ`, et "
        "`_rapport_par_nature`. "
        "CE QUI CHANGE D'OBSERVABLE, et il faut le dire : le champ "
        "`RapportSuppression.fichiers_par_nature` "
        "(`Mapping[str, tuple[str, ...]]`) est REMPLACE par "
        "`fichiers_a_supprimer: tuple[str, ...]`, une liste plate de chemins "
        "relatifs POSIX dans l'ordre ou l'appelant les a construits. Le "
        "rapport perd la CLASSIFICATION, jamais l'INFORMATION : le cardinal "
        "et les chemins restent lisibles, et les trois appelants "
        "(`_retirer_un_objet_versionne`, `_retirer_un_tirage` et "
        "`remove_project_element` lui-meme -- NEUF sites) posent le meme "
        "champ. Tout le reste est intact : `fichiers_non_supprimes`, "
        "`fichiers_attendus_absents`, les codes de sortie, le manifeste "
        "ecrit AVANT les fichiers (AC 10) et la double confirmation du "
        "dernier lot (`EPIC11-ARB-89`). "
        "MOTIF MESURE : `projects/` n'est plus versionne du tout depuis le "
        "2026-09-03 (CLAUDE.md, section Git LFS), donc tout fichier de projet "
        "tombait en `NATURE_NON_SUIVI` PAR CONSTRUCTION -- le classement ne "
        "discriminait plus rien, et l'avertissement qu'il alimentait cote CLI "
        "se declenchait toujours alors que sa promesse ecrite etait « il "
        "n'apparait que quand c'est vrai ». "
        "L'HISTOIRE DU `git rm -r` DU 2026-08-27 RESTE ECRITE au docstring de "
        "module : c'est le motif qui justifie l'existence d'une suppression "
        "propre, et il survit au retrait -- ce qui part, c'est la logique qui "
        "INSPECTAIT git. "
        "SUPERSESSION NOMMEE : `EPIC11-ARB-89` exigeait verbatim, a son point "
        "3, que la commande « distingue pointeur LFS / fichier local / "
        "donnees de travail non suivies ». `EPIC11-ARB-199` prime -- "
        "posterieur, d'Egan, et visant nommement cette clause. Une ligne de "
        "supersession a ete posee dans "
        "`decisions-2026-08-30-epic11-arb-89-sorties-nommees.md`. "
        "MESURE PAR `tests/unit/test_frontiere_git_hors_du_coeur.py` (banc "
        "neuf : trois frontieres AST, chacune avec son volet de morsure, dont "
        "celle des litteraux d'OCTETS qu'un balayage `str` seul ne verrait "
        "pas) et par `test_suppression_element_de_projet.py`, dont trois "
        "tests de classement sont retires et deux tests neufs poses."
        "\n\n"
        "2026-09-07, MEME FICHIER, AUTRE LOT -- retirer un jeu de frames "
        "EXTRAITES seul : AJOUT PUR. Retour de terrain d'Egan du 2026-09-06, "
        "verbatim : « on ne peut pas retirer d'un projet un jeu de frames "
        "extraites sans emporter autre chose ». "
        "CE QUI CHANGE : `remove_project_element` gagne le mot-cle "
        "`frames_extraites=False`, cinquieme cible fine ; `RapportSuppression` "
        "gagne `rang_independant=True` ; `_FamilleVersionnee` gagne "
        "`rang_independant=True` et `contenant=\"lot\"`. Les trois defauts "
        "reprennent le comportement d'avant au caractere pres, ce qui est "
        "MESURE et non affirme : `test_suppression_element_de_projet.py` (289 "
        "verts, dont les cinq bancs de commande et la frontiere des champs du "
        "rapport, qui a rougi sur le champ neuf et a ete etendue AVEC SA "
        "RAISON) et `test_le_drapeau_au_repos_ne_change_RIEN_au_chemin_du_lot_"
        "entier`, qui joue `frames_extraites=False` sur la suppression du lot "
        "entier. "
        "POURQUOI DANS LE COEUR ET PAS DANS LA TUI : la TUI n'appelle le coeur "
        "que par le coeur heberge (`EPIC11-ARB-1`), et l'operation traverse "
        "les deux gardes de chemin PAYEES de ce module -- "
        "`_sous_le_projet` (un `frames_dir` valant `\".\"` emportait "
        "`project.json` lui-meme) et `_refuser_le_chevauchement` (un "
        "`frames_dir` valant l'ancetre commun ramassait les frames de TOUS les "
        "lots). Un ecran qui composerait la suppression lui-meme les rouvrirait "
        "toutes les deux. Elle ecrit aussi le manifeste AVANT les fichiers "
        "(AC 10) et le RESTAURE sur echec partiel : un protocole que rien hors "
        "du coeur ne peut tenir. "
        "CE QUE LE CHANGEMENT NE REPARE PAS, dit plutot que tu : (1) le jeu de "
        "frames extraites n'est PAS un sixieme objet versionnable et ne le "
        "devient pas -- son dossier est nomme par le `version_rank` du LOT "
        "(`extraction._build_lot`), donc `--version` et `--liberer-le-rang` y "
        "sont REFUSES nommement plutot qu'honores, et aucun champ de ligne "
        "d'eau neuf n'est pose ; (2) `state` n'est pas ramene en arriere -- une "
        "reextraction sur un lot avance passe par l'ecrasement conscient, qui "
        "est une issue mais reste un geste de plus ; (3) les champs du plan "
        "d'extraction (`expected_frame_count`, timecodes, condensat) SURVIVENT "
        "au retrait : ils viennent de la selection, jamais d'un comptage sur "
        "disque, et un lecteur qui les prendrait pour une preuve de presence "
        "se tromperait -- seul `frames_dir` designe le dossier."
        "\n\n"
        "`EPIC11-ARB-264` (tranche par Egan par invite le 2026-09-07, sur son "
        "constat de terrain du 2026-09-06 : « planches (l'ensemble) et masters "
        "(l'ensemble d'un lot) ne sont pas selectionnables »), MEME FICHIER, "
        "AUTRE LOT : AJOUT PUR de `remove_project_group`, `RapportDeGroupe` et "
        "`LigneDeGroupe`. Aucune signature existante n'est touchee, et la "
        "boucle est AU-DESSUS de `remove_project_element` -- elle ne compose "
        "aucune cible et n'en juge aucune : un groupe n'existe pas au coeur "
        "(`project_inventory` ne produit aucun noeud de regroupement) et "
        "`planche=True` vise UNE SEULE planche, donc il n'y a rien a elargir a "
        "l'interieur. "
        "SEMANTIQUE, verbatim de l'option choisie : « Au mieux, avec un compte "
        "rendu ligne par ligne. Le projet peut rester a moitie supprime, et il "
        "faut relancer en sachant ce qui reste. » Un refus n'annule pas les "
        "lignes precedentes et n'arrete pas les suivantes. "
        "POURQUOI DANS LE COEUR ET PAS DANS LA TUI : la TUI n'appelle le coeur "
        "que par le coeur heberge (`EPIC11-ARB-1`), et une boucle ecrite dans "
        "un ecran serait un jugement metier que le coeur ne porte pas "
        "(`EPIC11-ARB-30`) -- la CLI en a le meme besoin, et deux redactions de "
        "la meme sequence divergeraient sur la semantique d'echec, qui est "
        "justement ce que l'arbitrage vient de fixer. "
        "CE QUE LE CHANGEMENT NE REPARE PAS : (1) il n'y a AUCUNE annulation "
        "dans le depot -- ni corbeille ni journal rejouable a l'envers --, "
        "donc « plus dur a annuler » est ce qu'Egan attend, pas ce que le "
        "produit offre ; (2) le tout-ou-rien n'etait pas implementable "
        "honnetement et le document le mesure : rien ne remet un fichier "
        "detruit ni un dossier passe au `rmtree`, si bien qu'annuler la seule "
        "moitie manifeste produirait un manifeste declarant des fichiers "
        "disparus ; (3) le GROUPE DES SCANS n'est pas traite -- un scan porte "
        "son consentement propre (`EPIC11-ARB-90`), et l'empiler N fois sous un "
        "seul geste est une question de consentement, pas d'echec partiel, et "
        "elle n'a pas ete posee.",
    "src/mixed_media_utility/io/payload.py":
        "Story 11.7, `EPIC11-ARB-176` et `-178` : AJOUT PUR d'une fonction, "
        "`sheets_pdf_filename_from_payload`, qui reconstruit le nom d'un "
        "tirage a partir de la charge utile decodee d'un code-barres. "
        "MOTIF, verbatim d'Egan le 2026-09-02 : « la fonction qui decode a "
        "toutes les cles pour savoir le nom de la planche dont est issu un "
        "scan ? En utilisant les memes infos et LE MEME SYSTEME DE NOMMAGE ? » "
        "-- « le meme systeme de nommage » est ce qui commande la forme : la "
        "fonction APPELLE `io.naming.build_sheets_pdf_filename`, elle ne "
        "recompose jamais la chaine a cote. Une seconde redaction de la "
        "convention divergerait en silence le jour ou l'une des deux change, "
        "et c'est exactement le defaut que le renommage des tirages "
        "(`EPIC11-ARB-171`) rendait imminent. "
        "AUCUNE SIGNATURE EXISTANTE N'EST TOUCHEE, et c'est la propriete qui "
        "compte : `build_page_payload`, `payload_version_rank` et les gardes "
        "de validation rendent les memes valeurs qu'avant. Ce que le module "
        "gagne est un appelant de plus pour `payload_version_rank`, qui n'en "
        "avait AUCUN dans `src/` -- le rang traversait deja l'impression, le "
        "papier et le decodage, et s'arretait juste avant d'etre ecrit. "
        "MESURE PAR `tests/unit/test_payload_naming_roundtrip.py` (dont une "
        "frontiere negative a l'AST : l'unique `return` de la fonction EST "
        "l'appel au constructeur -- compter les appels ne suffirait pas) et "
        "`tests/unit/test_scan_manifest.py`. Commits `8fb443e5` et "
        "`e051b2a0`.",
    "src/mixed_media_utility/gui/atelier_scan.py":
        "Story 11.14, lot D2 (`EPIC11-ARB-222`), commit `631c1c0` : AUCUNE "
        "SIGNATURE N'EST TOUCHEE -- `cardinal_des_frames_ecrites` garde son "
        "nom, sa signature et son contrat. Ce qui change est la RACINE qu'elle "
        "compte. "
        "MOTIF, verbatim du docstring que ce commit ecrit : « Les DEUX racines "
        "sont comptees. Un projet deja sur disque porte ses frames scannees "
        "sous la racine d'avant, un projet neuf sous `SCAN_FRAMES_DIRNAME`, et "
        "aucun des deux n'est converti. N'en compter qu'une rendrait ce "
        "cardinal systematiquement nul sur les projets d'avant -- c'est-a-dire "
        "un contrat C qui annonce "
        "\u00ab aucune frame ecrite \u00bb alors que le scan vient d'en "
        "ecrire. » Le comptage passe donc de "
        "`project_layout.OUTPUT_FRAMES_DIRNAME` a "
        "`project_layout.racines_de_frames_scannees`, qui possede la regle de "
        "cohabitation et ne rend l'ancienne racine que si elle existe -- donc "
        "aucun double comptage. "
        "POURQUOI CETTE ENTREE EST ECRITE PAR LE LOT D1 ET NON PAR D2, dit "
        "plutot que tu : `tests/unit/tui/` est le perimetre exclusif du lot "
        "D1 de la meme story, et le lot D2 n'avait donc pas le droit d'y "
        "ecrire. La garde a rougi entre les deux lots -- comportement voulu, "
        "elle exige qu'un changement de coeur soit JUSTIFIE, pas qu'il soit "
        "interdit --, et le motif ci-dessus est celui que D2 a lui-meme "
        "ecrit dans le code, relu au diff `4f441ba..631c1c0`, jamais devine.",
    "src/mixed_media_utility/extraction_previz.py":
        "Story 11.14 (`EPIC11-ARB-214`, `EPIC11-ARB-220`), commit "
        "`24ad3dfb3` : AUCUNE SIGNATURE N'EST TOUCHEE, et le changement ne "
        "porte meme sur AUCUNE ligne executable -- une seule ligne de "
        "DOCSTRING, le renvoi croise `io/project_layout.frames_dir` qui "
        "devient `io/project_layout.extract_frames_dir`. "
        "MOTIF : la fonction visee a ete renommee par le lot B ; un renvoi "
        "qui nomme une fonction disparue envoie le lecteur suivant chercher "
        "un symbole qui n'existe plus, ce qui est le defaut exact que la "
        "story 11.14 retire -- un mot pour un objet, y compris quand le mot "
        "est dans un commentaire. "
        "POURQUOI L'ENTREE ARRIVE APRES LE COMMIT : meme motif que ses deux "
        "voisines ci-dessous -- le commit a mesure les bancs du module "
        "touche, pas cette garde-ci, et c'est le lot E2 qui l'a trouvee en "
        "mesurant son perimetre. C'est le comportement VOULU de la garde : "
        "elle rougit d'un changement non consigne, pas d'un defaut. "
        "VERIFIE AU DIFF, jamais devine : `git diff 289f29d -- "
        "src/mixed_media_utility/extraction_previz.py` rend une seule "
        "insertion et une seule suppression, toutes deux dans la docstring "
        "de `build_extraction_previz`.",
    "src/mixed_media_utility/scan_output_frames.py":
        "Story 11.14 (`EPIC11-ARB-89`, `EPIC11-ARB-220`), commit `dea3247` : "
        "AUCUNE SIGNATURE N'EST TOUCHEE -- le changement porte sur le TEXTE "
        "d'un seul refus, `resolve_output_frames_version_rank`, et sur le "
        "commentaire qui l'accompagne. "
        "MOTIF MESURE, et ce n'est pas une coquille de vocabulaire : le refus "
        "de rangs epuises proposait comme issue `mmu project remove --lot "
        "<id> --frames <rang>`, drapeau que le lot C venait de RETIRER "
        "(`--frames` -> `--frames-scannees`, retrait pur). Un refus qui nomme "
        "une sortie INEXISTANTE est un blocage sec deguise, c'est-a-dire une "
        "violation d'`EPIC11-ARB-89` -- « un refus qui n'offre aucune issue "
        "est aussi fautif qu'une destruction silencieuse » --, et elle vivait "
        "dans le commentaire meme qui disait l'eviter. Le libelle « frames "
        "rescannees » passe au meme endroit a « frames scannees », le mot "
        "d'Egan. "
        "TROUVE PAR UNE FRONTIERE, PAS PAR UNE RELECTURE : "
        "`test_conformite_sorties_nommees.py::"
        "test_tout_drapeau_cite_dans_un_message_EXISTE_sur_SA_commande` a "
        "rougi dessus. Un renommage d'option traverse les modules qui ne sont "
        "dans AUCUN lot, et rien d'autre ne les regarde. "
        "MESURE APRES : 7 verts sur cette frontiere, 208 sur "
        "`tests/unit/test_scan_output_frames.py`. "
        "POURQUOI CETTE ENTREE ARRIVE APRES LE COMMIT et non avec lui : le "
        "meme motif que `project_inventory.py` ci-dessous -- le commit a "
        "mesure les bancs du module touche, pas cette garde-ci, et c'est le "
        "lot D1 qui l'a trouvee en mesurant `tests/unit/tui/` en entier. "
        "C'est le comportement voulu de la garde.",
    "src/mixed_media_utility/project_inventory.py":
        "Story 11.11, lot A : FICHIER NEUF, et il est de COEUR par exigence "
        "explicite de son AC 1 -- « un point d'entree de coeur rend "
        "l'INVENTAIRE, et la TUI ne le derive pas ». Le placer sous `tui/` "
        "aurait ete l'inverse de ce que la story demande : l'ecran doit LIRE "
        "un inventaire, jamais le recalculer, sans quoi il en existerait deux "
        "lectures qui divergeraient. "
        "AUCUNE SIGNATURE EXISTANTE N'EST TOUCHEE, et c'est la propriete qui "
        "compte : le module n'ajoute que `inventorier_le_projet()` et son "
        "vocabulaire publie (`NATURES`, `ETATS`, `REFUS_DU_COEUR`). Il "
        "EMPRUNTE sa filiation a `project_maintenance` -- masters, tirages et "
        "scans -- plutot que d'en ecrire une seconde, ce qu'`EPIC11-ARB-108` "
        "exige (« il n'y a pas de mecanisme different par objet »), et un "
        "test d'accord le confronte a "
        "`remove_project_element(dry_run=True)` sur le meme lot. "
        "MESURE PAR `tests/unit/test_inventaire_de_projet.py` (63 tests), "
        "dont la frontiere AST qui interdit au module d'importer `cli` et son "
        "volet symetrique. "
        "POURQUOI CETTE ENTREE ARRIVE APRES LE COMMIT du lot et non avec lui : "
        "le lot a mesure `test_frontiere_cli` (467 verts) mais pas cette "
        "garde-ci, et c'est la suite complete de la vague qui l'a trouvee. "
        "C'est le comportement voulu de la garde -- elle mord sur un "
        "changement de coeur legitime et exige qu'il soit JUSTIFIE, pas "
        "qu'il soit interdit.",

    "src/mixed_media_utility/declaration_de_rush.py":
        "Story 11.4e, lot A : FICHIER NEUF, 655 lignes, et c'est le point "
        "d'entree de coeur que le depot n'avait pas. "
        "MOTIF MESURE (`EPIC11-ARB-131`) : ajouter un rush etait CIRCULAIRE -- "
        "`rushes[]` n'etait ecrit que par `persist_extraction`, qui exige un "
        "`ExtractionRecord` complet (selection de frames, cadence cible, "
        "entree `lots[]`), donc un rush n'entrait dans un projet qu'en etant "
        "EXTRAIT. Aucune sous-commande de `mmu` ne le declarait, et `relink` "
        "REPOINTE la source d'un rush deja declare, ce qui n'est pas la meme "
        "chose. Le lot B (`mmu project add-rush`) et le lot C (l'ecran "
        "`Ajouter un rush` de `E2-1`) appellent ce module ; la TUI l'atteint "
        "sans passer par `cli`, ce que la frontiere de la 11.4b exige. "
        "MESURE : `tests/unit/test_declaration_de_rush.py`, 60 tests, "
        "campagne de 37 mutants dont 5 poses par la liaison elle-meme -- "
        "37 tues, zero survivant. Le survivant `L4` a tenu jusqu'a ce qu'on "
        "voie POURQUOI : aucun rush de `tests/fixtures/rushes/` ne pouvait le "
        "tuer, ils corroborent tous leur `nb_frames`. Ferme par un probe de "
        "synthese parametre et trois regimes de non-corroboration.",

    "src/mixed_media_utility/source_confirmation.py":
        "Story 11.4e, lot A : +110 lignes. `lire_la_source(probe)` et le "
        "dataclass `LectureDeLaSource` sont extraits pour que la DECLARATION "
        "d'un rush lise une source exactement comme l'extraction la lit. "
        "MOTIF MESURE : sans cette extraction, la declaration aurait sa "
        "propre lecture de probe, et deux lectures d'un meme artefact "
        "divergent -- c'est le mode de panne que le depot a paye sur le "
        "vocabulaire partage de l'aide de champ (revue 11.9, couche 1 `F4`, "
        "mutant `M55` : trois ecrans disaient la meme chose avec trois mots). "
        "`build_source_report` reste le seul producteur du rapport normalise "
        "pour le manifeste. "
        "POURQUOI CETTE ENTREE ARRIVE APRES LE COMMIT du lot et non avec lui, "
        "et c'est la MEME cause que l'entree precedente : le lot a mesure ses "
        "propres bancs (541/541 sur sept bancs) mais pas cette garde-ci, que "
        "la course de vague a trouvee. La garde fait son travail.",

    "src/mixed_media_utility/qr_codes.py":
        "`EPIC11-ARB-250` et `-251` (Egan par invite, 2026-09-06) : "
        "`encode_qr_image` encode par `segno` et non plus par "
        "`cv2.QRCodeEncoder`, puis RELIT son propre symbole et avertit sans "
        "bloquer. "
        "MOTIF MESURE, et il sort du perimetre de l'Epic 11 parce que le "
        "defaut y est anterieur : la ligne 4.10/4.11 d'OpenCV produit un "
        "symbole MALFORME au-dela de la version 7, et le produit encode entre "
        "les versions 12 et 18. Une planche imprimee depuis un tel poste porte "
        "un QR qu'AUCUN lecteur ne relira jamais -- controle croise : un "
        "symbole encode par 4.10 est illisible par 4.12, par 5.0 et par "
        "`zxing-cpp` qui n'est pas OpenCV, tandis qu'un symbole encode par 5.0 "
        "est lu CONFORME par 4.10. Le detecteur de 4.10 est sain ; c'est son "
        "encodeur qui ne l'est pas. "
        "POURQUOI PAS UN PLANCHER DE VERSION, qui aurait laisse le coeur "
        "intact : `4.10.0.84` est la DERNIERE version portant une roue "
        "`macosx_12_0_x86_64`. Tout plancher au-dessus sortait macOS 12 de la "
        "compatibilite -- objection d'Egan, mesuree et retenue. `segno` est "
        "pur Python (`py3-none-any`), donc sans plateforme. "
        "CE QUI REND LA BASCULE SURE : 0 ecart de cote sur 80 comparaisons "
        "cote a cote contre l'ancien encodeur, donc la geometrie d'impression "
        "est INCHANGEE -- aucun gabarit, aucune reserve, aucun seuil de "
        "calibration touche. Sous 4.10, chemin reel : 21/21 decodes contre "
        "1/21. Detail dans "
        "`_bmad-output/implementation-artifacts/decisions-2026-09-06-epic11-encodeur-qr.md`.",

    "src/mixed_media_utility/io/version_ranks.py":
        "Correction du 2026-09-06 : `cardinal_des_homonymes()` neuve, et "
        "c'est une entree que la garde a EXIGEE a juste titre. "
        "MOTIF MESURE : le lot `E2-1j` avait fait importer "
        "`VERSION_RANK_MAX` par `tui/ajout_de_rush.py` pour le formater dans "
        "une phrase. La frontiere "
        "`test_versionnage_du_scan_en_tui.py::test_AUCUN_module_de_la_TUI_ne_redige_une_regle_de_RANG` "
        "l'a attrape, et elle avait raison SUR LE FOND et pas seulement sur "
        "la lettre : le coeur porte deja `refus_de_rangs_epuises`, donc "
        "l'ecran ne lisait pas une borne, il recomposait une regle -- ce "
        "qu'`EPIC11-ARB-108` interdit (« il n'y a pas de mecanisme different "
        "par objet »). "
        "Le cardinal se calcule donc la ou la regle des rangs est ecrite une "
        "fois pour tous, et la TUI l'APPELLE. Elle ne porte plus aucun mot du "
        "vocabulaire des rangs. L'ecart entre les deux comptes -- l'original "
        "porte un nom sans rang, d'ou un homonyme de plus que de rangs -- est "
        "desormais documente la ou il se calcule, et non en commentaire dans "
        "un ecran, c'est-a-dire du mauvais cote de la frontiere.",

    "src/mixed_media_utility/io/calibration_profile.py":
        "`EPIC11-ARB-225` (renommage `patches/` -> `planches/`, 2026-09-06) : "
        "`VERSIONS_DIRNAME` cesse d'etre une chaine litterale de ce module et "
        "devient `project_layout.VERSIONS_DIRNAME`. Le nom reste exporte ici "
        "pour ses appelants -- aucune signature ne bouge, aucune valeur ne "
        "change. "
        "MOTIF MESURE : le module portait sa PROPRE declaration de "
        "`\"versions\"`, c'est-a-dire exactement le litteral double que "
        "`project_layout` existe pour fermer -- son commentaire "
        "d'`OUTPUTS_DIRNAME` l'enonce mot pour mot. Deux declarations, c'est "
        "un renommage qui n'en deplace qu'une et rien qui rougisse ; le "
        "renommage de la nuit a justement montre trois resolveurs dans ce "
        "regime.",

    "src/mixed_media_utility/io/pdf_manifest.py":
        "`EPIC11-ARB-225`, meme renommage : **un mot de commentaire**, "
        "`patches/` -> `planches/`, dans la note qui explique pourquoi le "
        "chemin vient de l'appelant. Zero ligne executable. "
        "POURQUOI CETTE ENTREE EXISTE QUAND MEME : la frontiere ne lit pas la "
        "nature d'une ligne, et c'est voulu -- un commentaire qui nomme "
        "l'ancien dossier est precisement ce qui fait recomposer le mauvais "
        "chemin a la story suivante. Le report est sans risque et sans "
        "discussion.",

    "src/mixed_media_utility/video_metadata.py":
        "Deux passes de DOCSTRING, aucune ligne executable (2026-09-06, puis "
        "correction du 2026-09-07 sur finding de la couche 3 de la revue du "
        "lot F). "
        "MOTIF MESURE : l'en-tete declarait « ffmpeg/ffprobe version measured "
        "for this module: 6.1.1 » sans qu'aucun releve d'execution y soit "
        "adosse. Sous FFmpeg 8, un master est sorti en `color_space=bt709` "
        "avec `color_primaries` et `color_transfer` vides -- la garde a EU "
        "RAISON de refuser le fichier, mais son rapport ne nommait aucune "
        "version, donc il ne designait pas la cause. C'est la meme lecon que "
        "`CLAUDE.md` tire du QR : « une mesure de comportement produit nomme "
        "la version de la bibliotheque sous laquelle elle a ete prise ». "
        "La seconde passe RETIRE ce que la premiere affirmait a tort : le "
        "releve de version ne va PAS au manifeste. `encode_manifest_fields` "
        "est gelee a l'octet par le dossier d'identite d'`encode`, et un "
        "agent qui aurait suivi la premiere redaction aurait fait rougir onze "
        "scenarios d'identite. Le texte disait l'inverse du code du meme "
        "commit.",

    # ----------------------------------------------------------------------
    # LIAISON DE L'EPIC 8 (2026-09-07, `bdc2226a`) -- six fichiers de coeur.
    #
    # Aucun n'est le fait d'une story de l'Epic 11 : ils viennent de la
    # branche d'empaquetage, et c'est EXACTEMENT l'usage que le commentaire
    # de tete de ce registre decrit -- « la garde a mordu pour de vrai [...]
    # et pas sur une story de l'Epic 11 ». Inscrits un par un, avec leur
    # motif, plutot que par un deplacement de la ligne de base : celui-ci
    # aurait exempte les 41 fichiers de coeur du meme mouvement, dont ceux
    # que les stories de l'Epic 11 ont bel et bien touches entre-temps
    # (`EPIC11-ARB-264` cote coeur, `CALIB-N1` cote coeur, entre autres).
    # C'est-a-dire qu'il aurait relache la garde en pretendant la renforcer.
    # ----------------------------------------------------------------------
    "src/mixed_media_utility/io/manifest.py":
        "Livraison Epic 8, 2026-09-07 : la resolution des schemas JSON passe "
        "de `parents[3] / \"_bmad-output\" / \"specs\"` a `parents[1] / "
        "\"specs\"`. Aucune signature ne bouge -- trois constantes de chemin, "
        "et rien d'autre. "
        "MOTIF MESURE : depuis un clone, `parents[3]` tombe sur la racine du "
        "depot et tout marchait ; depuis un `site-packages`, il tombe sur "
        "`lib/python3.x/` et `validate_manifest` levait un "
        "`FileNotFoundError`. Roue construite puis installee dans un venv "
        "neuf : ZERO fichier `.json` embarque sur 88. Les 18 000 tests ne "
        "l'ont jamais vu parce qu'ils tournent tous DEPUIS le depot. "
        "`parents[1]` vaut le paquet, vrai des deux cotes.",

    "src/mixed_media_utility/specs/project.schema.json":
        "Livraison Epic 8, 2026-09-07 : FICHIER NEUF, et c'est un DEPLACEMENT "
        "depuis `_bmad-output/specs/`, octet pour octet. Le schema devient une "
        "DONNEE DU PAQUET, que hatchling embarque avec le module. Voir le "
        "motif de `io/manifest.py` ci-dessus : sans ce deplacement, "
        "`pip install mmu-tui` livre un outil qui ne sait pas valider un "
        "manifest.",

    "src/mixed_media_utility/specs/project.schema.v2-0.json":
        "Livraison Epic 8, 2026-09-07 : meme deplacement que "
        "`project.schema.json`, meme motif. Le contrat v2.0 est lu par "
        "`io/manifest.py` sur le meme chemin de resolution ; le laisser hors "
        "du paquet aurait fait echouer la seule branche de compatibilite.",

    "src/mixed_media_utility/specs/project.schema.legacy.json":
        "Livraison Epic 8, 2026-09-07 : meme deplacement, meme motif. Le "
        "schema legacy est celui qu'ouvre la lecture d'un projet ancien -- "
        "c'est-a-dire le chemin le PLUS probable chez un utilisateur qui "
        "installe l'outil pour reprendre un travail existant.",

    "src/mixed_media_utility/gui/jetons.py":
        "Livraison Epic 8, 2026-09-07 : DEUX LIGNES DE DOCSTRING, zero ligne "
        "de code. La source de verite citee en tete du module passe de "
        "`_bmad-output/planning-artifacts/ux-designs/.../DESIGN.md` a "
        "`docs/guide-developpeur/DESIGN.md`. "
        "MOTIF MESURE (`EPIC11-ARB-268`) : le depot public ne porte que les "
        "chemins de `_bmad-output/` que les bancs lisent -- une citation qui "
        "designe un fichier reste prive mene le lecteur d'un clone public "
        "vers rien. Le fichier a ete DEPLACE, pas copie : une seule source de "
        "verite subsiste.",

    "src/mixed_media_utility/io/metadata_matrix.py":
        "Livraison Epic 8, 2026-09-07 : UNE LIGNE DE DOCSTRING, zero ligne de "
        "code. Meme mouvement et meme motif que `gui/jetons.py` -- la "
        "citation d'`ARCHITECTURE_DETAILED.md` suit le fichier dans "
        "`docs/guide-developpeur/`.",
}

#: **La ligne de base a ete remontee a la LIAISON du 2026-09-01** (`4f441ba`,
#: merge de 142 commits de `main`), et c'est un renforcement, pas un
#: relachement.
#:
#: La liaison amene dix-huit fichiers de coeur modifies -- `version_ranks.py`,
#: `project_maintenance.py`, `encode.py`, `scan_output_frames.py`... Aucun
#: n'est le fait d'une story de l'Epic 11 : ils viennent de `main`, ou d'autres
#: agents les ont ecrits. Les inscrire un par un dans `CHANGEMENTS_ACCEPTES`
#: aurait EXEMPTE ces dix-huit fichiers **pour toujours** : une story de
#: l'Epic 11 qui en toucherait un demain passerait sans rougir, et c'est
#: exactement ce que cette garde existe pour empecher. Deplacer la ligne de
#: base les remet tous sous surveillance a partir de l'etat que la branche
#: vient d'adopter.
#:
#: Ce que le deplacement coute, dit plutot que tu : les entrees de
#: `CHANGEMENTS_ACCEPTES` ci-dessus qui portent sur des changements ANTERIEURS
#: a la liaison ne designent plus de fichier modifie -- elles sont absorbees
#: dans la ligne de base. Elles sont gardees comme trace ecrite du chemin
#: parcouru, pas comme tolerances vivantes ; seules celles qui nomment la
#: liaison ou ce qui la suit ont encore un effet.
#: **Une SECONDE remontee, a la liaison du 2026-09-07 (`417979f4b`), a ete
#: ecrite puis MESUREE puis RETIREE.** Elle est gardee ici comme trace,
#: parce que le raisonnement qui l'a produite est le meme que celui du
#: paragraphe ci-dessus et qu'il faut savoir pourquoi il ne vaut pas ici.
#:
#: Le deplacement de 2026-09-01 se justifiait parce que les dix-huit
#: fichiers d'alors venaient TOUS de `main`. La population de la liaison
#: du 2026-09-07 est MIXTE : porter la ligne de base a `417979f4b`
#: exempterait les 41 fichiers de coeur du meme intervalle -- 307 commits
#: touchant `src/` --, dont ceux que des stories de l'Epic 11 ont bel et
#: bien touches entre-temps, `87c23754` (« EPIC11-ARB-264, coeur ») et
#: `f41a22a7` (« CALIB-N1 fermee cote coeur ») parmi d'autres. Le meme
#: geste relacherait donc la garde en pretendant la renforcer.
#:
#: Les six fichiers de coeur de cette liaison-la sont inscrits UN PAR UN
#: dans `CHANGEMENTS_ACCEPTES` ci-dessus, avec leur motif mesure. C'est
#: exactement l'usage que le commentaire de tete du registre decrit.
BASELINE = "4f441ba"


def test_une_fonction_du_coeur_tourne_pendant_que_l_ecran_reste_dessine(banc):
    """AC 5.1 : l'assertion porte sur l'arbre PENDANT l'appel, pas apres.

    La fonction appelee est une vraie fonction du coeur, prise chez
    `io.naming` : un double de test ne dirait rien de l'hebergement.
    """
    observations = {}

    async def scenario(pilote):
        app = pilote.app

        def au_coeur(valeur):
            # Ici, le coeur tourne. On regarde l'ecran depuis l'interieur.
            observations["zones"] = sorted(
                w.id for w in app.screen.walk_children() if w.id)
            observations["bandeau"] = app.screen.query_one(
                "#bandeau", Static).content
            return derive_short_id(valeur)

        return app.executer_en_processus(au_coeur, "un_rush_au_nom_tres_long" * 4)

    rendu = banc(CoqueTui(), scenario)
    assert observations["zones"] == ["bandeau", "centre", "etat", "raccourcis"]
    assert observations["bandeau"].startswith("mmu ·")
    # Et le resultat du coeur traverse intact : la coque ne le reinterprete pas.
    assert rendu == derive_short_id("un_rush_au_nom_tres_long" * 4)
    assert len(rendu) <= CANONICAL_ID_MAX_LENGTH


def test_executer_en_processus_laisse_passer_les_erreurs_du_coeur(banc):
    """Volet symetrique : la coque ne mange pas l'echec qu'elle heberge.

    Un appel qui avalerait l'exception rendrait la TUI muette sur un refus du
    coeur -- exactement ce que `EPIC11-ARB-30` interdit dans l'autre sens.
    """
    async def scenario(pilote):
        def au_coeur():
            raise ValueError("identifiant refuse")
        with pytest.raises(ValueError, match="identifiant refuse"):
            pilote.app.executer_en_processus(au_coeur)
        return True

    assert banc(CoqueTui(), scenario) is True


@pytest.mark.parametrize("interdit", LANCEURS_INTERDITS)
def test_aucun_lanceur_de_processus_dans_le_paquet_tui(interdit, sources_tui):
    """AC 5.2, frontiere : comptage a zero, un nom a la fois.

    La seule exception est celle de `LANCEURS_TOLERES`, nommee par fichier ET
    par nom : un module tolere pour `subprocess` reste coupable pour les sept
    autres, et les autres modules restent coupables pour les huit.
    """
    coupables = {chemin.name for chemin in sources_tui
                 if interdit in identifiants(chemin)
                 and interdit not in LANCEURS_TOLERES.get(chemin.name, ())}
    assert not coupables, f"{interdit} reference dans {sorted(coupables)}"


def test_la_TOLERANCE_est_bornee_a_UN_module_et_a_UN_nom():
    """Volet symetrique de la tolerance elle-meme.

    Sans lui, elargir `LANCEURS_TOLERES` a tout le paquet -- ou aux huit noms --
    passerait toutes les mesures ci-dessus en restant vert. La tolerance est un
    arbitrage borne (`EPIC11-ARB-85`), pas une porte.
    """
    assert set(LANCEURS_TOLERES) == {"execution.py"}, LANCEURS_TOLERES
    assert LANCEURS_TOLERES["execution.py"] == ("subprocess",)
    for nom in LANCEURS_INTERDITS:
        if nom == "subprocess":
            continue
        assert nom not in LANCEURS_TOLERES["execution.py"], nom


def test_le_module_TOLERE_n_a_QU_UN_SEUL_site_de_lancement():
    """`EPIC11-ARB-85`, forme imposee : « **un seul** site d'appel, nomme ».

    Mesure par AST sur les **references** a un lanceur, et non sur les appels :
    le module passe `subprocess.run` par valeur (`lancer = subprocess.run if
    lancer is None else lancer`), pour que les bancs puissent l'observer sans
    monkeypatch. Un banc qui chercherait un `Call` y trouverait zero site et
    serait vert sur un module qui en porterait dix. `subprocess.DEVNULL` et
    `subprocess.SubprocessError`, eux, ne lancent rien et ne comptent pas.
    """
    from mixed_media_utility.tui import execution

    arbre = ast.parse(Path(execution.__file__).read_text(encoding="utf-8"))
    lanceurs = ("run", "call", "check_call", "check_output", "Popen")
    lancements = [
        noeud for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Attribute)
        and isinstance(noeud.value, ast.Name)
        and noeud.value.id == "subprocess"
        and noeud.attr in lanceurs
    ]
    assert len(lancements) == 1, (
        f"{len(lancements)} sites de lancement dans execution.py : la "
        "tolerance d'EPIC11-ARB-85 n'en accorde qu'UN")
    assert lancements[0].attr == "run", (
        f"le lanceur est `subprocess.{lancements[0].attr}` : la tolerance "
        "porte sur un appel qui ATTEND la main et rend un code retour, pas "
        "sur un processus lache dans la nature")


def test_ce_qui_est_LANCE_est_un_OUVREUR_DE_BUREAU_et_jamais_le_depot():
    """`EPIC11-ARB-85`, seconde moitie de la forme : « son argument est **un
    chemin de dossier**, jamais un module du depot ni une commande ».

    Les trois commandes sont lues sur les **valeurs** de la table du module, et
    confrontees a la liste blanche : une table qui gagnerait `python`,
    `sys.executable` ou `mmu` rougirait ici, et c'est exactement l'invariant
    que l'AC 5.2 continue de garder.
    """
    from mixed_media_utility.tui import execution

    toutes = set(execution.COMMANDE_D_EXPLORATEUR_PAR_DEFAUT)
    for commande in execution.COMMANDES_D_EXPLORATEUR.values():
        toutes.update(commande)
        assert len(commande) == 1, (
            f"{commande} porte des arguments : la tolerance n'accorde qu'un "
            "ouvreur suivi du chemin, rien d'autre")
    assert toutes <= OUVREURS_DE_BUREAU, sorted(toutes - OUVREURS_DE_BUREAU)

    # Et ce qui part REELLEMENT : l'argv est mesure, pas relu. Deux systemes,
    # pour que la table soit exercee ailleurs que sur sa seule entree par
    # defaut (regle des fabriques).
    for systeme, attendu in (("linux", "xdg-open"), ("darwin", "open")):
        vus = []
        dossier = Path(tempfile.mkdtemp())
        execution.ouvrir_dans_l_explorateur_du_systeme(
            dossier, systeme=systeme,
            lancer=lambda argv, **kwargs: vus.append(argv))
        assert vus == [[attendu, str(dossier)]], vus
        assert not any(mot in vus[0][0] for mot in
                       ("python", "mmu", "mixed_media_utility")), vus


def test_le_lancement_NE_LEVE_JAMAIS_quand_aucun_bureau_ne_repond():
    """`EPIC11-ARB-85`, troisieme point de la forme : « il **rend une phrase**
    quand aucun bureau n'est joignable, il ne leve jamais ».

    C'est le regime NOMINAL de ce depot -- un conteneur sans bureau --, donc le
    volet qui compte le plus. Les trois pannes possibles sont exercees, et
    chacune rend une phrase qui NOMME le chemin : c'est ce qui reste utilisable
    a la main.
    """
    from mixed_media_utility.tui import execution

    dossier = Path(tempfile.mkdtemp())
    for panne in (FileNotFoundError("xdg-open"),
                  PermissionError("refuse"),
                  subprocess.TimeoutExpired("xdg-open", 10)):
        def lancer(argv, **kwargs):
            raise panne

        phrase = execution.ouvrir_dans_l_explorateur_du_systeme(
            dossier, systeme="linux", lancer=lancer)
        assert str(dossier) in phrase, (type(panne).__name__, phrase)
        assert "xdg-open" in phrase, (type(panne).__name__, phrase)

    # Un dossier disparu se dit AVANT l'appel : l'ouvreur n'est pas lance du
    # tout, sinon le gestionnaire ouvrirait sa propre erreur, que la TUI ne
    # verrait jamais passer.
    vus = []
    absent = dossier / "parti"
    phrase = execution.ouvrir_dans_l_explorateur_du_systeme(
        absent, systeme="linux", lancer=lambda argv, **k: vus.append(argv))
    assert vus == [], vus
    assert str(absent) in phrase, phrase


@pytest.mark.parametrize("interdit", LANCEURS_INTERDITS)
def test_la_mesure_des_lanceurs_mord_sur_un_module_fautif(tmp_path, interdit):
    """AC 5.2, volet symetrique, sur les huit noms et pas sur le premier."""
    chemin = tmp_path / "module_fautif.py"
    chemin.write_text(
        f'"""Un docstring qui parle de {interdit} sans l\'appeler."""\n'
        f'import os, subprocess\n'
        f'def lancer():\n'
        f'    return os.{interdit} if hasattr(os, "{interdit}") '
        f'else subprocess.{interdit}\n',
        encoding="utf-8")
    assert interdit in identifiants(chemin)


def test_le_paquet_tui_n_importe_rien_qui_lance_un_processus(sources_tui):
    """Meme frontiere, prise par les imports : `import subprocess` seul suffit
    a trahir l'intention, meme sans appel."""
    for chemin in sources_tui:
        if "subprocess" in LANCEURS_TOLERES.get(chemin.name, ()):
            continue                    # `EPIC11-ARB-85`, voir la table
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        modules = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                modules.update(a.name.split(".")[0] for a in noeud.names)
            elif isinstance(noeud, ast.ImportFrom) and noeud.module:
                modules.add(noeud.module.split(".")[0])
        assert "subprocess" not in modules, chemin.name


def _fichiers_modifies(racine_depot, depuis: str) -> list[str]:
    resultat = subprocess.run(
        ["git", "diff", "--name-only", f"{depuis}..HEAD", "--",
         "src/mixed_media_utility"],
        cwd=racine_depot, capture_output=True, text=True)
    if resultat.returncode != 0:
        pytest.skip(f"git indisponible ou {depuis} inconnu : {resultat.stderr}")
    return [ligne for ligne in resultat.stdout.splitlines() if ligne.strip()]


def _cles_du_registre(source: str) -> list[str]:
    """Les cles de `CHANGEMENTS_ACCEPTES` telles que le LITTERAL les porte.

    **Ecrit une fois, appele par les DEUX tests qui suivent** (finding `P20` de
    la revue de la story 6.7). Le volet "qui MORD" reecrivait auparavant cette
    logique au lieu de l'appeler : il prouvait donc qu'**une** detection marche,
    jamais que **la** frontiere marche. Mesure de la couche 3 : degrader le
    seuil de la frontiere reelle (`> 1` en `> 2`, donc aveugle a un doublon
    simple) laissait **27 verts, zero rouge** -- le volet symetrique n'avait pas
    bouge d'un pouce, puisqu'il ne mordait pas dessus.

    La lecture porte sur le litteral et non sur le dictionnaire construit : ce
    dernier a deja perdu le doublon quand on l'interroge. C'est la difference
    entre mesurer la source et mesurer son resultat, et ici seule la premiere
    voit quoi que ce soit.
    """
    litteral = None
    for noeud in ast.walk(ast.parse(source)):
        if (isinstance(noeud, ast.AnnAssign)
                and getattr(noeud.target, "id", "") == "CHANGEMENTS_ACCEPTES"):
            litteral = noeud.value
            break
    assert litteral is not None, "CHANGEMENTS_ACCEPTES introuvable dans la source"
    return [cle.value for cle in litteral.keys]


def _doublons_du_registre(source: str) -> list[str]:
    """Les cles presentes plus d'une fois dans le litteral, triees."""
    cles = _cles_du_registre(source)
    return sorted({cle for cle in cles if cles.count(cle) > 1})


def test_AUCUNE_cle_de_CHANGEMENTS_ACCEPTES_n_est_DUPLIQUEE():
    """**Le seul defaut de ce registre qui ne fait rougir rien du tout.**

    Python ne refuse pas deux fois la meme cle dans un litteral de
    dictionnaire : il garde SILENCIEUSEMENT la derniere. Un agent qui ajoute
    une entree pour un module deja present -- geste naturel quand le fichier
    est loin et le registre long -- efface donc le motif de son predecesseur
    sans qu'aucune mesure ne bouge. Le registre resterait vert, la frontiere du
    diff resterait verte, et le motif perdu ne manquerait a personne avant le
    report.

    La mesure porte donc sur le LITTERAL, lu par `ast`, et non sur le
    dictionnaire construit -- qui a deja perdu le doublon quand on l'interroge.
    C'est la difference entre mesurer la source et mesurer son resultat, et ici
    seule la premiere voit quoi que ce soit.

    Le volet symetrique : le cardinal des cles lues doit egaler celui du
    dictionnaire importe. Une lecture d'arbre qui ne trouverait plus le bon
    noeud rendrait une liste vide, et l'egalite ci-dessus serait verte sans
    rien observer.
    """
    source = SOURCE_DU_REGISTRE.read_text(encoding="utf-8")
    cles = _cles_du_registre(source)
    doublons = _doublons_du_registre(source)
    assert doublons == [], (
        f"cles dupliquees dans CHANGEMENTS_ACCEPTES : {doublons}. Python garde "
        "la derniere en silence, donc le motif de la premiere est PERDU. Un "
        "module deja present gagne un paragraphe DANS son entree, il n'en "
        "ouvre pas une seconde.")

    # Volet symetrique : la lecture a bien vu tout le litteral.
    assert len(cles) == len(CHANGEMENTS_ACCEPTES), (len(cles),
                                                    len(CHANGEMENTS_ACCEPTES))


def test_la_mesure_des_DOUBLONS_mord_sur_un_registre_fautif(tmp_path):
    """Volet symetrique, sur un litteral fabrique pour etre fautif.

    La frontiere ci-dessus est verte aujourd'hui, et une frontiere verte ne
    prouve rien tant qu'on n'a pas vu ce qui la fait rougir. Le registre
    fabrique ici porte **trois** entrees et le doublon est **au milieu** : une
    detection qui ne comparerait que la premiere et la derniere cle, ou qui
    s'arreterait au premier ecart, resterait verte dessus.

    Et il porte deux MOTIFS DIFFERENTS sous la meme cle, parce que c'est le
    degat reel : le dictionnaire construit ne garde que le second, si bien que
    le premier motif a disparu sans laisser de trace.
    """
    faux = tmp_path / "registre_fautif.py"
    faux.write_text(
        "CHANGEMENTS_ACCEPTES: dict[str, str] = {\n"
        '    "src/a.py": "le motif de A",\n'
        '    "src/b.py": "le PREMIER motif de B -- celui qui est perdu",\n'
        '    "src/b.py": "le second motif de B",\n'
        "}\n",
        encoding="utf-8")

    source = faux.read_text(encoding="utf-8")
    # **Le MEME helper que la frontiere**, jamais une copie de sa logique : une
    # degradation du seuil, du noeud cherche ou de la portee du `walk` rougit
    # desormais ICI. C'est ce que le finding `P20` reprochait a ce test.
    cles = _cles_du_registre(source)
    assert _doublons_du_registre(source) == ["src/b.py"], cles

    # Et voici le degat, dit plutot que suppose : le dictionnaire construit a
    # perdu le premier motif sans que rien ne l'ait signale.
    construit = ast.literal_eval(ast.parse(source).body[0].value)
    assert len(construit) == 2 < len(cles)
    assert construit["src/b.py"] == "le second motif de B"


#: Le seul fichier du coeur qu'une RELEASE fait bouger, et il n'est pas un
#: changement de coeur : il ne porte que `__version__`.
#:
#: **Pourquoi une exemption structurelle plutot qu'une entree au registre**
#: (pose le 2026-09-09, a la release v0.1.1). `CHANGEMENTS_ACCEPTES` existe
#: pour les changements de coeur de l'Epic 11 -- un par un, avec leur motif, et
#: chacun doit gagner sa ligne dans la table de liaison. Une release n'est ni
#: l'un ni l'autre : elle **recommencera a chaque version**, elle ne se
#: reporte sur aucune branche (une release se refait, elle ne voyage pas), et
#: le banc de liaison ne sait de toute facon pas reconnaitre `__init__` comme
#: un module de coeur. Y mettre la version aurait fait rougir DEUX frontieres
#: a chaque release, et une garde qui rouge a chaque release cesse d'etre lue.
#:
#: **L'exemption est bornee par une MESURE, pas par une promesse** : le test
#: jumeau ci-dessous verifie que ce fichier ne porte rien d'autre qu'une
#: affectation de `__version__`. Le jour ou du code y entre, l'exemption cesse
#: d'etre sure et le banc le dit -- au lieu de couvrir en silence un vrai
#: changement de coeur.
FICHIER_DE_VERSION = "src/mixed_media_utility/__init__.py"


def test_le_fichier_de_VERSION_ne_porte_QUE_sa_version(racine_depot):
    """La borne de l'exemption `FICHIER_DE_VERSION`, mesuree sur l'AST.

    `EPIC8-ARB-10` fait de ce fichier la source UNIQUE de version pour les deux
    distributions. Tant qu'il ne porte que cela, le voir bouger a une release
    n'apprend rien -- et quatre autres frontieres mesurent deja que toutes les
    declarations du depot la SUIVENT.
    """
    source = (racine_depot / FICHIER_DE_VERSION).read_text(encoding="utf-8")
    arbre = ast.parse(source)
    noms = []
    for noeud in arbre.body:
        if isinstance(noeud, ast.Expr) and isinstance(noeud.value, ast.Constant):
            continue                      # docstring
        if isinstance(noeud, ast.Assign):
            noms += [c.id for c in noeud.targets if isinstance(c, ast.Name)]
            continue
        noms.append(type(noeud).__name__)
    assert noms == ["__version__"], (
        f"{FICHIER_DE_VERSION} ne porte plus SEULEMENT `__version__` "
        f"({noms}). L'exemption de la garde de signature cesse d'etre sure : "
        "elle couvrirait un vrai changement de coeur en silence.")


def test_aucune_signature_du_coeur_n_a_bouge_depuis_le_baseline(racine_depot):
    """AC 5.3 et AC 7.2 : hors `tui/`, zero fichier modifie -- `cli.py` compris."""
    modifies = _fichiers_modifies(racine_depot, BASELINE)
    hors_tui = [c for c in modifies
                if "/tui/" not in c and c not in CHANGEMENTS_ACCEPTES
                and c != FICHIER_DE_VERSION]
    assert hors_tui == [], (
        "l'Epic 11 ne touche pas le coeur ; fichiers vus : "
        f"{hors_tui}. Si un changement est legitime, il s'inscrit dans "
        "CHANGEMENTS_ACCEPTES avec son motif.")


def test_la_mesure_du_diff_voit_bien_les_fichiers_de_la_tui(racine_depot):
    """AC 5.3, volet symetrique : la mesure n'est pas vide par accident.

    Si `git diff` ne rendait rien du tout, la garde ci-dessus serait verte sans
    rien mesurer. Le paquet `tui/` etant ne apres le baseline, il DOIT sortir.
    """
    modifies = _fichiers_modifies(racine_depot, BASELINE)
    assert any("/tui/" in chemin for chemin in modifies), modifies
