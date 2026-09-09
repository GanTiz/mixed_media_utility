"""Lire le SENS d'une planche : ce que ses symboles QR disent, pas ce que ses octets valent.

**Pourquoi ce module existe** (`EPIC11-ARB-250`, 2026-09-06). L'encodage QR est
passe d'OpenCV a `segno`. Les deux rendent le **meme cote** de symbole -- la
geometrie d'impression ne bouge pas d'un module -- mais **pas les memes
modules** : ils ne choisissent pas le meme masque de donnees. Le motif d'encre
change donc, a charge utile, version, niveau ECC et geometrie identiques.

Consequence : tout banc qui gele une planche **octet a octet** rougit, alors
que rien de ce que la planche *dit* n'a bouge. Deux bancs d'identite sont dans
ce cas (`test_identite_du_scan.py`, `test_makepdf_noyau.py`), et leur reference
est versionnee, produite par le `src/` d'un commit anterieur : la regenerer
detruirait ce qu'elle mesure.

**L'issue n'est pas d'excuser le condensat, c'est de le remplacer par une
egalite de SENS.** « Le scan n'a pas change de comportement » n'a jamais voulu
dire « l'encre a le meme motif » : il veut dire que la planche porte la meme
charge utile, donc que la chaine y lit la meme chose. Ce module rend cette
lecture, et les deux bancs s'en servent pour **conditionner** leur tolerance.

**Il lit par le chemin de la PRODUCTION**, jamais par un decodeur nu :
`scan_ingest` pour ouvrir (une image par `read_image_page`, un PDF par
`_open_pdf` + `_render_pdf_page`), `qr_codes.decode_qr_image_resilient` pour
decoder, `io.payload.parse_payload` pour interpreter. Un module qui lirait
autrement mesurerait un chemin que le produit n'emprunte pas.

**Ce qu'il NE fait pas, dit plutot que tu** : il ne dit rien de ce qui, sur la
planche, n'est pas un QR -- le nombre de pages, la position des zones de
frames, les pastilles de calibration, les libelles imprimes. C'est le banc
appelant qui doit tenir cela par ailleurs, et c'est exactement ce que la
mesure « un contenu change hors QR fait rougir » verifie.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[2]
if str(_RACINE / "src") not in sys.path:
    sys.path.insert(0, str(_RACINE / "src"))

from mixed_media_utility import page_roles, qr_codes, scan_ingest   # noqa: E402
from mixed_media_utility.io import payload as payload_io            # noqa: E402

#: L'absence d'une cle, distincte de toute valeur qu'une cle pourrait porter.
#: `None` ne conviendrait pas : un champ de payload vaut legitimement `None`.
_ABSENT = object()

#: Resolution de rasterisation d'un PDF avant decodage. 600 ppp est la consigne
#: de numerisation du produit (`qr_codes.QR_MIN_SCAN_DPI`) : rasteriser plus bas
#: mesurerait une planche que personne n'imprime, plus haut couterait sans rien
#: ajouter -- le symbole est vectoriel dans le PDF, il n'y a pas d'information a
#: gagner au-dela du seuil de decodage.
DPI_DE_RASTERISATION = qr_codes.QR_MIN_SCAN_DPI

#: Suffixes que ce module sait ouvrir. Un artefact d'un autre type n'est pas une
#: planche : il n'a pas de sens a lire, et la tolerance ne doit pas le couvrir.
SUFFIXES_LISIBLES = (".pdf", ".tif", ".tiff", ".png", ".jpg", ".jpeg")

#: Ce qu'on rend pour une page ou aucun symbole n'a ete decode. C'est une
#: VALEUR, pas une omission : une page qui perdrait son QR doit se voir dans la
#: comparaison, et une liste raccourcie en silence la ferait disparaitre.
AUCUN_SYMBOLE = "<aucun symbole decode>"


def est_lisible(chemin: Path | str) -> bool:
    """`chemin` a-t-il un suffixe que ce module sait ouvrir ?"""
    return Path(chemin).suffix.lower() in SUFFIXES_LISIBLES


def _pages_d_un_pdf(chemin: Path) -> list:
    document = scan_ingest._open_pdf(chemin)
    try:
        return [
            scan_ingest._render_pdf_page(document, index, DPI_DE_RASTERISATION)
            for index in range(len(document))
        ]
    finally:
        document.close()


def pages_de_l_artefact(chemin: Path) -> list:
    """Les rasters des pages de `chemin`, dans l'ordre du document."""
    chemin = Path(chemin)
    if chemin.suffix.lower() == ".pdf":
        return _pages_d_un_pdf(chemin)
    return [scan_ingest.read_image_page(chemin)]


def payloads_de_l_artefact(chemin: Path) -> tuple[str, ...]:
    """Les charges utiles decodees de `chemin`, une par page, dans l'ordre.

    Rend `AUCUN_SYMBOLE` pour une page dont le symbole ne se decode pas, plutot
    que de la sauter : le cardinal de la sequence est celui des pages, donc une
    page perdue et un symbole perdu sont deux ecarts distincts et tous deux
    visibles.
    """
    lus = []
    for page in pages_de_l_artefact(chemin):
        resultat = qr_codes.decode_qr_image_resilient(page)
        lus.append(resultat.text if resultat.ok else AUCUN_SYMBOLE)
    return tuple(lus)


def _aplatir(valeur, prefixe: str = "") -> dict:
    """Aplatir un payload en `chemin pointe -> scalaire`, comme le fait le releve."""
    if isinstance(valeur, dict):
        plat = {}
        for cle, feuille in valeur.items():
            plat.update(_aplatir(feuille, f"{prefixe}.{cle}" if prefixe else str(cle)))
        return plat
    if isinstance(valeur, list):
        plat = {}
        for index, feuille in enumerate(valeur):
            plat.update(_aplatir(feuille, f"{prefixe}[{index}]"))
        return plat
    return {prefixe: valeur}


def sens_de_l_artefact(chemin: Path) -> tuple[dict, ...]:
    """Le SENS de `chemin` : un payload APLATI par page, dans l'ordre.

    Un symbole illisible rend `{"<illisible>": AUCUN_SYMBOLE}` et un symbole
    dont le texte n'est pas un payload valide rend `{"<illisible>": <motif>}` --
    deux etats distincts d'un meme echec, et aucun des deux ne se confond avec
    un payload vide.
    """
    sens = []
    for texte in payloads_de_l_artefact(chemin):
        if texte == AUCUN_SYMBOLE:
            sens.append({"<illisible>": AUCUN_SYMBOLE})
            continue
        try:
            sens.append(_aplatir(payload_io.parse_payload(texte)))
        except payload_io.PayloadValidationError as motif:
            sens.append({"<illisible>": f"{type(motif).__name__}: {motif}"})
    return tuple(sens)


#: La reconnaissance, en une ligne : **un condensat d'artefact de l'arbre**. Le
#: reste de la famille ne se lit pas dans un chemin mais dans les octets du
#: fichier, et c'est le point -- une liste de chemins ecrite a la main serait
#: exactement ce que ce banc refuse ailleurs.
_MOTIF_DU_CONDENSAT_D_ARTEFACT = re.compile(r"^projet\.arbre\.(?P<artefact>.+)$")

_CONDENSAT_NU = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")

#: Les champs d'identite qu'un document de tri porte **au-dessus** de ses pages.
#: Ils sortent du QR de la page, comme le `page_index` : c'est ce que le
#: baseline a **lu** sur cette planche-la, projete dans son document.
IDENTITE_DU_LOT = ("project_id", "rush_id", "lot_id")

#: Les champs qu'un lot de manifest porte et qui valent pour **chacun** de ses
#: tirages. `template_id` n'en est PAS, et c'est mesure plutot que suppose : un
#: meme lot porte jusqu'a six `sheets_pdfs` de gabarits differents (`1f-por`,
#: `2f-por`, `4f-por`) alors que `lots[j].template_id` ne garde que le dernier.
#: L'y mettre ferait refuser cinq tirages sur six pour une raison fausse.
CHAMPS_STABLES_D_UN_LOT = ("lot_id", "rush_id", "patch_preset_id",
                           "gamut_map_id", "fps_target", "timecode_base_fps")


def _est_un_condensat(valeur) -> bool:
    return isinstance(valeur, str) and bool(_CONDENSAT_NU.match(valeur))


def _faits_du_baseline(reference: dict) -> tuple[dict, dict, set, dict]:
    """Ce que la REFERENCE dit avoir lu sur chaque planche, par quatre formes.

    Aucune de ces quatre formes ne nomme un scenario, un lot ni un chemin de
    fixture : chacune se reconnait a la **structure** d'un document aplati. Et
    aucune n'elit une valeur : ce qui est note ici est **empile**, puis reduit
    par `_consensus`, qui jette tout champ sur lequel deux scenarios ne disent
    pas la meme chose.

    1. **par le condensat** -- une page qui porte `<p>.source_digest` porte
       aussi, dans le meme document, tout le sous-arbre `<p>.payload.*` : c'est
       la charge utile ENTIERE que le baseline a decodee sur le fichier de ce
       condensat-la. C'est l'ancrage le plus fort, et le seul qui soit exact ;
    2. **par le chemin** -- une page qui porte `<p>.locator.source_path` porte
       souvent `<p>.page_index`, et son lot englobant porte son identite. C'est
       une **projection** de la charge utile, pas la charge utile : le tri ne
       recopie pas le payload, il en garde ce dont il se sert ;
    3. **par la chaine de calibration** -- un profil porte `chain_id` et
       `template_id` cote a cote, et ce `template_id` sort du QR de la page de
       calibration. C'est le seul temoignage que le baseline garde d'elle : le
       fichier de la page de calibration n'est nomme dans **aucun** document
       du dossier de reference (mesure : zero occurrence de `scans/calibration`
       dans les 42 scenarios) ;
    4. **par le manifeste du lot** -- un lot qui declare `sheets_pdfs[k].path`
       nomme un tirage, et porte a cote les champs stables du lot, qui sont
       ceux du QR de chacune de ses planches. C'est le seul temoignage que le
       baseline garde d'un TIRAGE : son chemin ne se retrouve ni par un
       condensat de source ni par un `locator`.

    Rend `(faits_par_condensat, faits_par_chemin, templates_de_calibration,
    identite_du_projet)`.
    """
    par_condensat: dict = {}
    par_chemin: dict = {}
    templates: set = set()
    projet: dict = {}

    def noter(table: dict, cle: str, faits: dict) -> None:
        """Empiler les valeurs observees, sans en elire aucune tout de suite."""
        vu = table.setdefault(cle, {})
        for champ, valeur in faits.items():
            vu.setdefault(champ, set()).add(valeur)

    for scenario in reference.values():
        documents = ((scenario.get("projet") or {}).get("documents") or {})
        for plat in documents.values():
            for cle, valeur in plat.items():
                segments = cle.split(".")
                prefixe = ".".join(segments[:-1])
                if segments[-1] == "source_digest" and isinstance(valeur, str):
                    tete = f"{prefixe}.payload."
                    charge = {suite[len(tete):]: feuille
                              for suite, feuille in plat.items()
                              if suite.startswith(tete)}
                    if charge:
                        noter(par_condensat, valeur.removeprefix("sha256:"),
                              charge)
                if (segments[-2:] == ["locator", "source_path"]
                        and isinstance(valeur, str)):
                    page = ".".join(segments[:-2])
                    faits = {}
                    if f"{page}.page_index" in plat:
                        faits["page_index"] = plat[f"{page}.page_index"]
                    lot = re.match(r"^(?P<lot>.*)\.pages\[\d+\]$", page)
                    if lot:
                        for champ in IDENTITE_DU_LOT:
                            if f"{lot.group('lot')}.{champ}" in plat:
                                faits[champ] = plat[f"{lot.group('lot')}.{champ}"]
                    if faits:
                        noter(par_chemin, valeur, faits)
                if segments[-1] == "chain_id":
                    voisin = f"{prefixe}.template_id" if prefixe else "template_id"
                    if isinstance(plat.get(voisin), str):
                        templates.add(plat[voisin])
                if (segments[-1] == "path" and isinstance(valeur, str)
                        and re.match(r"^(?P<lot>.*)\.sheets_pdfs\[\d+\]$",
                                     prefixe)):
                    lot = re.match(r"^(?P<lot>.*)\.sheets_pdfs\[\d+\]$",
                                   prefixe).group("lot")
                    faits = {champ: plat[f"{lot}.{champ}"]
                             for champ in CHAMPS_STABLES_D_UN_LOT
                             if f"{lot}.{champ}" in plat}
                    # Le RANG, lui, est propre a ce tirage-la et non au lot --
                    # c'est le seul fait du manifest qui distingue deux
                    # tirages du meme lot, dont tout le reste coincide. Il est
                    # absent pour le rang 1, que le manifest n'ecrit pas.
                    if f"{prefixe}.version_rank" in plat:
                        faits["version_rank"] = plat[f"{prefixe}.version_rank"]
                    if faits:
                        noter(par_chemin, valeur, faits)
                if cle == "project_id" and isinstance(valeur, str):
                    projet.setdefault("project_id", set()).add(valeur)
    return (_consensus(par_condensat), _consensus(par_chemin), templates,
            _consensus({"projet": projet}).get("projet", {}))


def _consensus(table: dict) -> dict:
    """Ne garder que les faits sur lesquels la reference ne se CONTREDIT pas.

    Un champ que deux scenarios remplissent differemment pour le meme artefact
    n'est pas un fait de cet artefact : c'est un champ qui a bouge dans le
    manifest **apres** que la planche a ete imprimee. Mesure : le manifest de
    `makepdf` reecrit `gamut_map_id` du lot a chaque passe, si bien que le
    tirage `..._2f-por.pdf` -- imprime en `gamut-map-none-1` -- se voyait
    attribuer le `gamut-map-lin-1` d'une passe ulterieure, et sept scenarios
    rougissaient pour un fait que la reference ne soutenait pas.

    Elire la derniere valeur vue aurait rendu le verdict dependant de l'ORDRE
    des scenarios ; en retirer le champ le rend dependant de ce que la
    reference AFFIRME. Le second est le seul des deux qui se mesure.
    """
    return {cle: {champ: valeurs.pop() for champ, valeurs in vus.items()
                  if len(valeurs) == 1}
            for cle, vus in table.items()}


def _index_par_condensat(travail: Path) -> dict:
    """`sha256 -> chemin` sur tout l'arbre de travail.

    On retrouve le fichier d'aujourd'hui **par son condensat**, jamais par son
    chemin : le chemin du releve est normalise (les noms de dossier ont ete
    traduits d'un cote), le condensat, lui, est ce que le releve compare.
    """
    index: dict = {}
    for chemin in sorted(travail.rglob("*")):
        if chemin.is_file():
            index.setdefault(
                hashlib.sha256(chemin.read_bytes()).hexdigest(), chemin)
    return index


class PlanchesAuMemeSens:
    """La cinquieme famille, en un objet : qui a le droit de changer d'octets.

    Il est construit **une fois** par module -- decoder 7 planches coute ~4 s --
    et il balaie lui-meme les 42 scenarios pour dresser, avant toute assertion,
    la table des condensats qu'il excuse. `au_meme_SENS` ne fait ensuite plus
    aucune lecture de fichier.
    """

    def __init__(self, reference: dict, releve: dict, travail: Path,
                 aplatir=_aplatir, ecarter=None) -> None:
        (self.faits_par_condensat, self.faits_par_chemin,
         self.templates_de_calibration,
         self.identite_du_projet) = _faits_du_baseline(reference)
        self.par_condensat = _index_par_condensat(travail)
        #: `condensat d'avant -> condensat d'aujourd'hui`, pour les seules
        #: planches dont le SENS est confirme. C'est la table de substitution.
        self.paires: dict = {}
        #: `(artefact, avant, apres) -> verdict`, y compris les refus : c'est
        #: ce que la mesure d'exactitude relit, et un refus qui disparaitrait
        #: s'y verrait. La cle porte le COUPLE de condensats et pas seulement
        #: l'artefact : une meme planche peut diverger deux fois sous deux
        #: couples (le scenario `36` en mute une pour la rendre perimee), et
        #: une cle par artefact ecraserait silencieusement l'un des deux.
        self.verdicts: dict = {}
        self._aplatir = aplatir
        #: Ce dont cet objet ne se prononce PAS, parce qu'une AUTRE famille de
        #: tolerance s'en charge deja. Rendre `True` retire le chemin du
        #: recensement -- il ne recoit ni verdict ni paire.
        #:
        #: **Pourquoi ce parametre existe, et il a ete paye** (2026-09-08, run
        #: 34222962404 de la CI publique, job 3.12). Le recensement balaie
        #: TOUT `projet.arbre.<artefact>` dont le condensat diverge, quel que
        #: soit l'artefact. Quand une autre famille excuse une divergence de
        #: raster -- la famille (h) de `test_identite_du_scan.py`, qui cesse de
        #: comparer les octets d'une frame extraite parce que ffmpeg dispatche
        #: son SIMD sur les capacites du CPU --, ces rasters entrent quand meme
        #: ici, y recoivent un REFUS (aucun QR a decoder), et font rougir la
        #: mesure d'exactitude de la cinquieme famille.
        #:
        #: Ce n'etait visible que sur une machine ou la divergence a lieu :
        #: 3.11 et 3.13 sont tombes sur des runners au comportement identique
        #: au baseline, 3.12 non. Une frontiere qui se prononce sur « ce qui a
        #: diverge » depend donc de la machine tant qu'elle n'est pas bornee a
        #: son propre perimetre.
        #:
        #: Le cout second etait mesurable : huit frames 4K sans symbole
        #: partaient dans `decode_qr_image_resilient` et sa boucle de sauvetage
        #: -- le job 3.12 a mis 35 min 27 la ou 3.11 et 3.13 en mettaient 26.
        self._ecarter = ecarter
        self._recenser(reference, releve)

    # -- le recensement, une fois pour toutes --------------------------------
    def _recenser(self, reference: dict, releve: dict) -> None:
        """Dresser la table des couples excuses, sur TOUS les scenarios."""
        for nom, attendu in reference.items():
            obtenu = releve.get(nom)
            if obtenu is None:
                continue
            a, b = self._aplatir(attendu), self._aplatir(obtenu)
            for chemin in set(a) | set(b):
                trouve = _MOTIF_DU_CONDENSAT_D_ARTEFACT.match(chemin)
                avant, apres = a.get(chemin, _ABSENT), b.get(chemin, _ABSENT)
                if not (trouve and _est_un_condensat(avant)
                        and _est_un_condensat(apres) and avant != apres):
                    continue
                if self._ecarter is not None and self._ecarter(chemin, avant,
                                                               apres):
                    continue
                artefact = trouve.group("artefact")
                verdict = self.porte_le_meme_SENS(artefact, avant, apres)
                self.verdicts[(artefact, avant, apres)] = verdict
                if verdict:
                    self.paires[avant] = apres

    # -- la decision, planche par planche ------------------------------------
    def porte_le_meme_SENS(self, artefact: str, avant: str, apres: str) -> bool:
        """La planche `artefact` dit-elle aujourd'hui ce que le baseline a lu ?

        Cinq conditions, et il les faut **toutes** :

        1. le suffixe est lisible -- un artefact qui n'est pas une planche n'a
           pas de sens a comparer, donc pas de tolerance ;
        2. le fichier d'aujourd'hui se retrouve par son condensat ;
        3. **chacune** de ses pages decode une charge utile valide -- un
           symbole illisible, ou un texte qui n'est pas un payload, refuse ;
        4. un document **pagine** porte autant de pages que ses symboles en
           declarent (`_le_CARDINAL_de_pages_est_celui_declare`) ;
        5. **chaque fait** que le baseline a note sur cette planche s'y
           retrouve, et le baseline en note **au moins un**. Une planche dont
           le baseline ne dit rien n'est pas excusee.

        Le point 5 se lit a deux portees, et c'est voulu. Un fait tenu **du
        condensat** vient du payload d'UNE page precise, donc il suffit qu'une
        page le confirme ; un fait tenu **du chemin** -- l'identite du lot, le
        rang du tirage -- vaut pour la planche entiere, donc **chacune** de ses
        pages doit le porter. Les confondre relacherait le second au niveau du
        premier : une planche dont une seule page porterait le bon rang
        passerait.
        """
        if not est_lisible(artefact):
            return False
        chemin = self.par_condensat.get(apres)
        if chemin is None:
            return False
        sens = sens_de_l_artefact(chemin)
        if not sens or any("<illisible>" in page for page in sens):
            return False
        if not self._le_CARDINAL_de_pages_est_celui_declare(chemin, sens):
            return False
        de_la_planche = self.faits_par_chemin.get(artefact, {})
        if de_la_planche and not all(
                page.get(cle, _ABSENT) == valeur
                for page in sens for cle, valeur in de_la_planche.items()):
            return False
        de_la_page = self.faits_par_condensat.get(avant, {})
        if de_la_page:
            return any(all(page.get(cle, _ABSENT) == valeur
                           for cle, valeur in de_la_page.items())
                       for page in sens)
        if de_la_planche:
            return True
        return all(self._est_une_MIRE_reconnue(artefact, page) for page in sens)

    @staticmethod
    def _le_CARDINAL_de_pages_est_celui_declare(chemin: Path,
                                                sens: tuple) -> bool:
        """Un document pagine porte-t-il toutes les pages que ses QR annoncent ?

        C'est la seule mesure de cette famille qui ne demande RIEN au baseline :
        chaque symbole declare le `page_count` de sa planche, donc une page
        retiree, ajoutee ou dupliquee se dit toute seule. Elle repond au mutant
        « une page en moins », que la comparaison des charges utiles, elle, ne
        verrait pas -- les pages restantes redisent toutes ce qu'elles doivent.

        **Elle ne vaut que pour un document pagine** (un PDF), et le dire vaut
        mieux que le taire : une image de scan est UNE page d'un dossier, son
        `page_count` compte les feuilles du lot et non les pages du fichier.
        Lui appliquer la regle la ferait refuser toujours.
        """
        if chemin.suffix.lower() != ".pdf":
            return True
        declares = {page.get("page_count") for page in sens}
        return declares == {len(sens)}

    def _est_une_MIRE_reconnue(self, artefact: str, page: dict) -> bool:
        """La page de calibration, seule planche dont AUCUN document ne parle.

        Ni son condensat ni son chemin n'apparaissent dans un document du
        dossier de reference -- mesure : zero occurrence, dans les deux
        dossiers d'identite. Une mire n'est d'ailleurs **pas** une planche de
        lot : son payload ne porte ni `project_id`, ni `lot_id`, ni `rush_id`
        (mesure : `page_de_calibration_autonome()` rend neuf champs, et aucun
        des trois n'y est). Il reste donc deux temoignages, et il en faut
        **un** :

        * **le profil que le baseline a consigne** atteste le `template_id`
          qu'il a lu sur une mire. C'est le cas du dossier du scan ;
        * **le NOM du tirage** porte le projet et le libelle de chaine, parce
          que c'est ainsi que le produit nomme une mire imprimee
          (`<projet>_<libelle-en-tirets>-<empreinte>_calibration.pdf`). Le nom
          est compare et vert par ailleurs : il atteste donc que le QU'ON A LU
          sur ce QR -- son `scan_chain_label` -- est bien celui de ce
          fichier-la. C'est le cas du dossier de `makepdf`, ou aucun profil
          n'est consigne.

        **C'est l'ancrage le plus faible de la famille, et il est nomme comme
        tel.** Ce qui le rattrape est ailleurs et vaut d'etre dit : le profil de
        calibration est **calcule sur les pixels des pastilles** de cette page,
        et ses coefficients sont compares champ a champ, hors tolerance, a
        seize decimales.
        """
        if page.get("page_role") != page_roles.PAGE_ROLE_CALIBRATION:
            return False
        if page.get("template_id") in self.templates_de_calibration:
            return True
        projet = self.identite_du_projet.get("project_id")
        libelle = page.get("scan_chain_label")
        if not (isinstance(projet, str) and isinstance(libelle, str)):
            return False
        return projet in artefact and libelle.replace(" ", "-") in artefact

    def porte_les_FAITS(self, condensat: str, attendus: dict) -> bool:
        """La planche de ce condensat redit-elle `attendus` sur CHACUNE de ses pages ?

        C'est `porte_le_meme_SENS` sans la recherche des faits : l'appelant les
        fournit, parce qu'il les tient d'un endroit que la forme ne sait pas
        atteindre. Le cas paye : un TIRAGE, dont le baseline ne dit rien par
        condensat ni par chemin -- son chemin a ete renomme par
        `EPIC11-ARB-171` --, mais dont le manifest du baseline decrit le lot
        champ a champ, et ces champs sont ceux du QR.

        La regle est ici **toutes les pages**, la ou `porte_le_meme_SENS` se
        contente d'une : les faits d'un lot valent pour chacune de ses
        planches, donc une page qui les contredirait est un defaut. Un
        `attendus` vide refuse -- une exigence vide serait vraie de tout.
        """
        chemin = self.par_condensat.get(condensat)
        if chemin is None or not attendus:
            return False
        sens = sens_de_l_artefact(chemin)
        if not sens or any("<illisible>" in page for page in sens):
            return False
        return all(page.get(cle, _ABSENT) == valeur
                   for page in sens for cle, valeur in attendus.items())

    # -- l'excuse, valeur par valeur -----------------------------------------
    def au_meme_SENS(self, avant, apres) -> bool:
        """`avant` ne devient-il `apres` QUE par des condensats deja excuses ?

        Une seule regle pour les trois formes ou un condensat de planche se
        montre : le condensat nu de l'arbre, le `source_digest` que le document
        de detection en RECOPIE, et les messages qui le CITENT (`stderr`, le
        journal). Toutes trois sont la meme substitution, et elle est exacte :
        si autre chose que ces condensats-la a bouge dans la valeur, l'egalite
        ne se referme pas et le chemin rougit.
        """
        if not (isinstance(avant, str) and isinstance(apres, str)):
            return False
        if avant == apres:
            return False
        substituee = avant
        for ancien, nouveau in self.paires.items():
            substituee = substituee.replace(ancien, nouveau)
        return substituee == apres


def chemins_au_sens_DIFFERENT(gauche, droite, planches=None) -> set:
    """Les chemins ou deux releves ne disent pas la meme chose, SENS compris.

    C'est la comparaison qu'un banc d'identite doit poser depuis
    `EPIC11-ARB-250` : deux planches dont seul le motif d'encre du QR differe
    ne sont pas deux planches differentes. Sans `planches`, elle rend la
    divergence brute -- une egalite d'octets, comme avant.

    Elle rend des **chemins** et non un booleen : un banc qui n'apprendrait que
    « ca diverge » ne pourrait pas nommer ou, et c'est ce que ce depot exige de
    toute assertion d'ensemble.
    """
    a, b = _aplatir(gauche), _aplatir(droite)
    return {chemin for chemin in set(a) | set(b)
            if a.get(chemin, _ABSENT) != b.get(chemin, _ABSENT)
            and not (planches is not None
                     and planches.au_meme_SENS(a.get(chemin, _ABSENT),
                                               b.get(chemin, _ABSENT)))}
