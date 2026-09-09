# Mixed Media Utility — Architecture detaillee

Date: 2026-07-20

## 1. Changement de modele

Le projet Mixed Media Utility n'est plus un workflow monomachine centre sur un dossier partage. Il devient un systeme local-first de transmission et de reconstruction de lots mixed media entre operateurs distincts, sur machines et arborescences distinctes.

Hypothese de travail:
- l'operateur A peut extraire des frames et produire un PDF imprimable;
- l'operateur B peut imprimer, transformer puis scanner ces pages sans avoir acces au dossier d'origine;
- l'operateur C peut reconstruire un projet local et encoder un media final a partir des scans et des metadonnees embarquees.

L'architecture doit donc porter un contrat de reconstruction explicite, independant des chemins d'origine.

## 2. Hierarchie des sources de verite

Ordre de priorite recommande:
1. manifest v2
2. payload QR
3. convention de nommage
4. texte lisible humain sur la page
5. metadonnees du conteneur video final

Regles:
- le manifest v2 est la source canonique complete;
- le QR code est la source reconstructive minimale;
- le nom de fichier est une redondance courte exploitable manuellement;
- les marqueurs ArUco sont reserves a la geometrie et, au maximum, a des roles discrets;
- les metadonnees video finales sont techniques et non metier.

## 3. Contrat minimal de reconstruction

Un lot doit etre reconstructible sur machine tierce si les elements suivants sont disponibles:
- scans de pages ou PDF de scan;
- QR code lisible sur chaque page;
- `schema_version` commune;
- identifiants stables `project_id`, `rush_id`, `lot_id`;
- `page_index`, `page_count`;
- `fps_target`;
- mapping ordonne `slot_index -> frame_timecode`;
- `template_id` et `patch_preset_id`.

Le manifest local doit pouvoir etre regenere a partir de ces donnees, meme s'il n'existe pas a l'arrivee.

### 3.1 Conventions d'indexation (normatif)

Ces conventions valent pour tous les canaux (manifest, QR, nom de fichier, code, tests). Elles sont
normatives: toute story qui manipule `page_index` ou `slot_index` s'y conforme sans re-arbitrage.

- `page_index` est **base zero**: la premiere page d'un lot porte `page_index = 0`, la derniere
  `page_count - 1`. L'invariant a verifier est donc `0 <= page_index < page_count`.
- `slot_index` est **base zero** et unique a l'echelle du lot (pas seulement de la page).
- `page_count` est un **cardinal**, pas un index: c'est le nombre de pages du lot, minimum 1.
- L'affichage humain (texte imprime sur la page, nom de fichier) peut presenter une numerotation
  base un pour rester lisible, a condition que la conversion soit explicite et faite au moment du
  rendu uniquement. Exemple: `build_frame_filename` emet `p001` pour `page_index = 0`. La valeur
  transportee dans le manifest et dans le payload QR reste toujours base zero.

> Note 2026-07-31 (checkpoint Epic 2): cette section est ajoutee a posteriori. Elle etait absente
> lors du developpement des stories 2.3 et 2.6, menees en branches paralleles, qui ont chacune
> choisi une base differente (2.3 base zero, 2.6 base un). Le defaut n'a ete detecte ni par les
> tests unitaires de 2.3 ni par ceux de 2.6, chacun validant sa propre convention sur des fixtures
> locales. Voir le test de bout en bout `tests/unit/test_payload_reconstruction_roundtrip.py`.

Ne font pas partie du contrat obligatoire:
- chemins absolus;
- nom de machine;
- emplacement du rush d'origine;
- etat du projet sur le poste source.

## 4. Contrat manifest v2 a viser

Le manifest v2 doit au minimum decrire:
- identite du projet;
- version de schema;
- lots et rushes avec identifiants stables;
- cadence source et cadence cible;
- resolution source et resolution cible;
- informations couleur utiles: primaries, transfer, colorspace, gamma ou equivalent normalise;
- template PDF utilise;
- preset de patchs;
- etat d'avancement du lot;
- artefacts generes localement;
- checksums ou empreintes courtes quand utiles pour verifier l'integrite.

Le manifest ne doit pas rendre obligatoires des chemins d'entree absolus. Les chemins internes doivent etre relatifs au projet local courant.

## 5. Matrice de responsabilite des metadonnees

| Donnee | Manifest | Nom de fichier | QR code | ArUco | Conteneur video final |
| --- | --- | --- | --- | --- | --- |
| `schema_version` | Oui | Non | Oui | Non | Non |
| `project_id` | Oui | Oui, version courte | Oui | Non | Optionnel |
| `rush_id` | Oui | Oui | Oui | Non | Optionnel |
| `lot_id` | Oui | Oui | Oui | Non | Non |
| `page_index` / `page_count` | Oui | Oui | Oui | Non | Non |
| `slot_index` | Oui | Optionnel | Oui | Oui, si discret seulement | Non |
| `frame_timecode` | Oui | Oui | Oui | Non | Optionnel |
| `fps_target` | Oui | Oui, forme courte | Oui | Non | Oui |
| `template_id` | Oui | Optionnel | Oui | Oui, si utile | Non |
| `patch_preset_id` | Oui | Non | Oui | Non | Non |
| parametres de marge / layout | Oui | Non | Oui, sous forme d'ID de preset | Non | Non |
| geometrie exacte des marqueurs | Oui, template | Non | Non | Oui, par detection visuelle | Non |
| resolution source / colorimetrie source | Oui | Non | Non | Non | Oui, partiel |
| resultats de calibration page | Oui | Non | Non | Non | Non |
| checksum des frames ou pages | Oui | Optionnel | Optionnel, court | Non | Non |
| codec cible / profil d'encode | Oui | Optionnel | Non | Non | Oui |
| provenance locale / chemins d'origine | Optionnel, non canonique | Non | Non | Non | Non |

Cette matrice est transcrite sous forme executable dans `src/mixed_media_utility/io/metadata_matrix.py` (story 2.4), avec des checks de coherence associes dans `tests/unit/test_metadata_matrix.py`.

### Note du 2026-08-08 (story 5.11): `template_id`, `patch_preset_id` et `gamut_map_id` atteignent le manifest **des l'impression**

La colonne « Manifest » marquait `template_id` et `patch_preset_id` « Oui »
depuis la story 2.4, mais **aucun producteur ne les ecrivait sur `lots[]`**:
l'ecart etait assume et date par EPIC4-ARB-4, qui ne posait pas une
interdiction permanente mais un report — « la persistance viendra par une story
de jonction dediee […] **tant que le scan n'en a pas besoin** ». La condition
est remplie: `gamut_map_id` doit atteindre le manifest pour que le scan le
**confronte** au lieu de le decouvrir (EPIC5-ARB-20). La matrice redevient donc
exacte des l'impression, sans qu'aucune ligne n'ait ete amendee.

Ce que `makepdf` ecrit desormais, apres generation reussie du PDF et rien
d'autre: `lots[].state = "pdf"`, `lots[].template_id`, `lots[].patch_preset_id`
et `lots[].gamut_map_id`. Trois points structurants:

* **`pdf` recoit son premier producteur sur le contrat v2.** La valeur existait
  dans `LOT_STATES` et dans l'enum du schema depuis la story 2.2, mais sa seule
  occurrence reelle etait `meta.lot.state` du manifest legacy du POC — un
  document sans `schema_version` et sans `lots[]`. La transition passe
  exclusivement par `validate_lot_state_transition`.
* **Un refus de la garde n'est pas une erreur ici**, contrairement a
  l'extraction. Reimprimer une planche perdue ou dechiree pour un lot deja
  scanne est le cas **nominal** de l'Epic 5: regenerer un PDF n'invalide aucun
  artefact aval, alors qu'une re-extraction reecrit les frames sous les
  artefacts deja produits. L'etat en place est conserve, le fait est nomme en
  information, la commande reussit.
* **Les trois identifiants vivent au niveau du lot, jamais dans la section
  `reconstruction`**, qui est unique par document et reecrite en entier a
  chaque appel: y loger une donnee qui varie d'un lot a l'autre rejouerait
  exactement le defaut que la v2.1 a corrige. `reconstruction.template_id`
  subsiste et garde son sens propre — la portee document de la chaine de
  reconstruction — sans etre la meme verite.

Les trois proprietes sont declarees dans `lots[].properties` du schema v2.1.
Ce n'est pas cosmetique: `lots[].items` est en `additionalProperties: false`,
donc un champ non declare **fait echouer la validation**, donc l'ecriture
atomique, donc la commande — apres que le PDF a ete ecrit.

### Note du 2026-08-11 (story 6.5): `encode` recoit son producteur, et la ligne « codec cible » de la matrice devient exacte

La ligne « codec cible / profil d'encode » de la matrice ci-dessus marque
`Manifest: Oui` depuis la story 2.4. Elle etait **fausse en pratique**:
`video.codec_target` etait declare au schema, classe critique par
`io.manifest.CRITICAL_PROJECT_FIELDS_V2_1`, et n'avait **aucun producteur** — au
point que `validate_manifest_completeness`, dont la docstring dit « before a
final encode », etait insatisfiable sur le manifest reel du depot, et ne butait
que sur ce champ-la. Elle l'a maintenant.

Ce que `encode` ecrit desormais, apres qu'un master a ete pose a son chemin
final et rien d'autre: `lots[].state = "encode"`, l'inventaire
`lots[].encoded_masters`, `video.codec_target` et `artifacts.outputs_dir`.
Quatre points structurants.

* **`encode` etait la derniere valeur de `LOT_STATES` sans ecrivain.** La 5.11 a
  comble `pdf`, la 5.7 `scan`; celle-ci ferme la table. La transition passe
  exclusivement par `validate_lot_state_transition`.
* **Un refus de la garde est ici une erreur dure**, contrairement a
  l'impression. La garde ne refuse jamais **par l'ordre** (`encode` est le
  maximum de la table, les six transitions sont acceptees) mais elle refuse par
  le **vocabulaire**, et ce refus est atteignable puisque `load_manifest` ne
  valide pas. Comme l'encode est terminal, conserver silencieusement une valeur
  hors vocabulaire la persisterait pour de bon. Divergence assumee avec
  `io.pdf_manifest`, qui conserve: le depot fait les deux, et l'harmonisation
  est consignee au `deferred-work.md`.
* **Un inventaire, et non un champ unique.** La commande produit deux masters
  distincts pour le **meme** profil (resolution par defaut et resolution
  native): un champ unique par profil detruirait l'existence du master
  mezzanine des qu'un derive est produit. La cle est le **chemin relatif**,
  unique par construction, et la liste est **triee** a l'ecriture —
  `sort_keys` canonise les mappings et pas les tableaux, si bien qu'un ordre
  d'insertion porterait l'ordre chronologique des encodages.
* **Le controle de version est sur le chemin d'ecriture, donc apres l'encodage.**
  Titre corrige en revue: il affirmait l'inverse de ce que fait le code, et son
  propre corps le contredisait. `_assert_mergeable` s'execute dans
  `persist_encode`, c'est-a-dire **apres** le retour d'`execute_plan`.
  `project.schema.v2-0.json` porte lui aussi `lots[].items` en
  `additionalProperties: false`: un document v2.0 non migre echouerait donc apres
  que la video a ete ecrite, et c'est ce que la migration en memoire evite. Le
  motif suivi est celui de la story 5.7 (legacy refuse, v2.0 migre en memoire,
  version inconnue refusee), pas celui de la 5.11, qui ne traite pas
  `schema_version`.
* **Ce qui a lieu avant l'encodage est une autre garde, et elle ne couvre pas
  les quatre cas de la meme facon.** `cli.encode_command` appelle
  `io.manifest.validate_manifest` en tete, avant `plan_encode`: cette validation
  refuse un manifest legacy, une `schema_version` inconnue et un `lots[].state`
  hors vocabulaire. Un document **v2.0 authentique**, en revanche, la
  **traverse** — le schema v2.0 le declare valide, c'est son role —, et c'est
  `plan_encode` qui le refuse, faute d'`output_frames_dir` sur le lot
  (`DOSSIER_DE_LOT_NON_DECLARE`). Mesure, pas deduction. Le contrat annonce
  (rien d'encode, code `1`) tient dans les deux cas; ce qui etait faux, dans
  trois documents a la fois, est le **qui refuse**. Ce que `validate_manifest`
  refuse en annoncant « 2.0 » est un document v2.1 re-etiquete, qui n'est pas le
  meme objet.
* **`video.codec_target` est de portee document alors que la decision est de
  portee lot.** Le schema n'offre pas d'autre emplacement, et
  `CRITICAL_PROJECT_FIELDS_V2_1` designe le champ au niveau document: encoder un
  seul lot satisfait donc le critere de completude « codec cible » pour tous les
  autres. Deplacer le champ serait un point de contrat de l'Epic 2. Ce que la
  story 6.5 ferme est le **silence**: le remplacement d'une valeur en place emet
  `CIBLE_D_ENCODAGE_REMPLACEE`, par symetrie avec `ENTREE_DE_MASTER_REMPLACEE`
  au niveau du lot. Corollaire a connaitre: l'idempotence octet a octet vaut pour
  deux `encode` identiques **du meme lot**; des qu'un projet melange deux
  profils, le document reste fonction de l'ordre des commandes.

Les proprietes d'`encoded_masters` sont declarees dans `lots[].properties` du
schema v2.1, avec `additionalProperties: false` sur l'entree elle-meme. Meme
raison qu'en 5.11, et le prix est plus eleve ici: un champ non declare fait
echouer la validation, donc l'ecriture atomique, donc la commande — apres que
**la video** a ete ecrite.

## 6. Recommandation QR code

Strategie retenue pour le MVP:
- un QR par page;
- payload de reconstruction minimal et stable;
- texte humain visible en clair sur la page.
- payload non compresse de facon opaque pour rester debuggable terrain.

Payload recommande:
- `schema_version`
- `project_id`
- `rush_id`
- `lot_id`
- `fps_target`
- `page_index`
- `page_count`
- `template_id`
- `patch_preset_id`
- `target_colorspace`
- liste des slots avec `slot_index` et `frame_timecode`

`page_index` et `slot_index` suivent les conventions d'indexation normatives de la section 3.1
(base zero). `target_colorspace` fait partie du payload minimal parce qu'il est la seule donnee
colorimetrique qu'un tiers peut recuperer sans acces au poste source: il doit etre propage
jusqu'au manifest reconstruit (`color.target_colorspace`), jamais consomme puis jete.

Hypotheses de dimensionnement pour lancer le dev:
- budget nominal de payload <= 512 octets UTF-8;
- plafond d'alerte a 768 octets;
- taille imprimee cible 30 mm de cote, minimum de travail 25 mm;
- noms lisibles `project_id` et `rush_id` plafonnes a 48 caracteres avant derive courte obligatoire dans les noms de fichiers.

A eviter:
- QR par frame des le MVP;
- payload compresse ou difficilement debuggable;
- dependance a une resolution serveur ou a une URL.

> Note 2026-07-21 (stories 4.3/4.6/5.5/6.2/6.3): essais synthetiques OpenCV (story 4.6) confirment le budget nominal (512 octets) et le plafond d'alerte (768 octets). Le "minimum de travail 25 mm" n'est plus interchangeable avec 30 mm: c'est un seuil de secours a risque, a documenter comme configuration degradee si utilise; 30 mm est la cible fiable confirmee. A taille imprimee fixee, un ECC eleve (H) est moins robuste au flou/bruit uniforme qu'un ECC M ou Q, car concu pour des dommages localises et non une degradation globale — ECC Q est retenu comme defaut provisoire. Ces seuils restent bases sur des essais synthetiques, a valider par un vrai pilote d'impression/scan avant fermeture definitive.

> Note 2026-08-11 (story 5.17, `EPIC5-ARB-60` — **le payload passe en `2.0` et les cles
> raccourcissent**). La liste de champs ci-dessus reste le contrat *semantique*; ce qui
> est **imprime** porte desormais des cles de deux a trois caracteres: `sv`, `pid`, `rid`,
> `lid`, `pi`, `pc`, `fps`, `tid`, `ppi`, `tcs`, `gmi`, `s`, et dans chaque emplacement
> `si` et `ft`. La table est unique, nommee `io.payload.PAYLOAD_SHORT_KEYS`, et
> consommee par la serialisation **et** par le parsing; le dictionnaire manipule par le
> depot garde ses noms longs. Gain mesure en encodant reellement le symbole: 362 -> 246
> octets au cardinal 1, **698 -> 442 au cardinal 8**, soit 32 % a 37 %.
>
> Trois consequences qui depassent la place gagnee. (1) Le budget nominal de 512 octets
> n'est plus atteint par aucun cardinal du vocabulaire (pire cas 442), la ou 6f et 8f
> vivaient sur le plafond d'alerte. (2) Le plafond dur de 768 octets n'est plus
> atteignable par **aucun** lot composable: la page la plus lourde du registre pese 563
> octets. (3) La version 22 du symbole QR (105 modules), que `QRCodeDetectorAruco` ne
> decode a aucune taille imprimee, sort du domaine atteignable par un cardinal du
> vocabulaire — mais la garde reste due et elle est livree:
> `qr_codes.QR_BANNED_SYMBOL_VERSIONS`, appliquee par `check_print_geometry` quel que
> soit le ratio px/module.
>
> Il n'existe **aucun lecteur bi-format**: une planche imprimee sous `1.0` cesse d'etre
> scannable et doit etre reimprimee. `parse_payload` le dit avec un motif nomme, distinct
> du refus d'un QR etranger sans cle de version. La borne de 48 caracteres sur
> `project_id` / `rush_id` n'est **pas** relevee: elle est motivee par la lisibilite des
> noms de fichiers, jamais par le budget QR — les cles courtes retirent seulement le QR
> de la liste des raisons de la garder basse.


## 7. Recommandation ArUco

Strategie retenue:
- ArUco pour detection, orientation, homographie et localisation des zones utiles;
- IDs reserves a des roles discrets si necessaire: coin, slot, variante de template.

A ne pas faire:
- encoder dans les IDs ArUco des informations riches comme timecode, marge, nombre de patchs, nom de rush ou fps;
- faire d'ArUco le canal principal de reconstruction metier.

> Note 2026-07-21 (stories 4.3/4.6/5.5/6.2/6.3): dictionnaire `DICT_6X6_250` et taille marqueur 30 mm confirmes par sweep synthetique (story 4.3), marge confortable meme en degradation extreme. Politique "4 coins obligatoires, aucun fallback affine" confirmee et justifiee: une distorsion projective (cause typique de perte d'un coin: page non plane, angle de prise de vue) ne peut pas etre corrigee par un affine a 3 points, ce qui produirait une geometrie fausse silencieusement. Un seul dictionnaire ArUco par page: les roles (coin obligatoire, variante de template, slot) se distinguent par plages d'IDs reservees, jamais par changement de dictionnaire.

> **Rectificatif 2026-08-02 (code review story 4.3).** Voir ARCHITECTURE.md section 7
> pour le detail. En resume: (a) `DICT_6X6_250` / 30 mm confirme **pour DPI >= 150**,
> mais "marge confortable meme en degradation extreme" ne vaut pas sur l'ensemble du
> sweep (92/180 en `extreme`, 62/180 en `brutal`); (b) le sweep ne peut pas fonder le
> **choix** du dictionnaire (rendu natif 400 px biaise en faveur de 6X6); (c) aucun
> seuil de taille **imprimee** n'a ete mesure (mm et DPI sont le meme axe); (d) la
> politique "4 coins obligatoires" est necessaire mais **pas suffisante** — deux modes
> de corruption silencieuse (homographie de rang deficient sur centres quasi alignes,
> ID de coin duplique ecrase) ont ete trouves et corriges, avec rejet explicite via
> `PageGeometryError` et ses sous-classes; (e) le risque terrain dominant est la
> contamination de la **quiet zone**, pas l'occlusion du marqueur.

> **Note 2026-08-05 (story 4.4, decision d'encodage ArUco — EPIC4-ARB-5).** La
> question laissee ouverte par le brief ("faisabilite d'encoder plusieurs
> parametres utiles dans les IDs ArUco") est **fermee: repartition ArUco + QR**,
> aucun encodage de donnees dans les IDs. Chiffrage qui clot les trois candidats:
> (a) **index de frame** — un lot porte jusqu'a 1000 images (ARB-10) et
> `slot_index` est unique a l'echelle du lot (section 3.1): aucun dictionnaire de
> 250 IDs ne peut le porter, et le QR transporte deja le mapping complet
> `slot_index -> frame_timecode` (story 2.3); (b) **marge discrete** — l'interdit
> de la presente section et la colonne "Non" de la matrice (section 5) portent
> sur les **parametres bruts** de marge et sont **confirmes**: la marge vit dans
> le QR comme preset de template (`template_id`). Nuance de perimetre (revue
> 4.4): porter une **variante de template** par ArUco n'est pas interdit — la
> matrice dit `template_id` ArUco "Oui, si utile" et la plage 10..19 est reservee
> a cet usage — c'est ecarte par la decision pour les memes motifs que le reste
> (divergence de sources, cout de surface), pas par interdit; (c) **nombre de
> patchs** — propriete de `patch_preset_id` (registre 4.7), transporte par le QR.
> Cout de surface qui ecarte tout marqueur additionnel: estimation prudente
> ~60x60 mm par marqueur en milieu de page (symbole 30 mm + marge de silence
> reprise de `MARKER_MARGIN_MM` = 15 mm sur les quatre cotes — valeur de
> conception, **pas une mesure**: le rectificatif 4.3 ci-dessus dit explicitement
> qu'aucun seuil en mm n'a ete mesure, seule la contamination de quiet zone en
> pixels l'a ete), pour un benefice nul tant que le QR est lisible et insuffisant
> quand il ne l'est pas (un ID seul ne reconstruit rien; le repli reste texte
> humain puis nom de fichier, story 4.6/4.2).
> **Politique d'impression MVP**: seuls les 4 coins sont imprimes —
> `layout.PRINTED_MARKER_IDS`, consommee par le generateur de planche et
> verrouillee par test. Les plages reservees (variantes 10..19, slots 20..49)
> restent dormantes, sans producteur ni consommateur.
> **Politique de detection pour la story 5.2**: la copie **normative** est le
> bloc de contrat de `src/mixed_media_utility/layout.py` (au-dessus de
> `PRINTED_MARKER_IDS`); le present resume s'y subordonne en cas de divergence.
> En bref: coins = obligatoires (4/4, doublon -> `AmbiguousMarkersError`);
> marqueur d'une plage reservee ou non assignee detecte sur un scan MVP =
> **ignore pour la geometrie + avertissement** nommant l'ID et son role (planche
> voisine dans le champ, feuille d'un futur template) — jamais injecte dans
> l'homographie (deja effectif et verrouille par test; l'avertissement reste a
> produire par 5.2, voir deferred-work.md). La story qui activera une plage
> reservee devra aussi statuer ce que signifie l'absence d'un marqueur attendu
> de cette plage. Les zones de frames se localisent par l'homographie des 4
> coins + la geometrie du template resolue depuis `template_id` lu dans le QR.
> La matrice narrative de la section 5 est confirmee sans amendement; sa
> transcription executable (`io/metadata_matrix.py`) portait en revanche
> `slot_index` ArUco en REQUIRED la ou le narratif dit "Oui, si discret
> seulement" — ramenee a OPTIONAL par la revue 4.4.

## 8. Pipeline image et couleur

Pipeline effectivement retenu pour le MVP:
1. accepter en entree des scans image ou PDF convertibles, sans exiger un format unique;
2. lire l'image dans son espace de travail disponible;
3. detecter les marqueurs ArUco sur l'image scannee;
4. redresser completement la page;
5. extraire les frames reconstruites;
6. exporter les frames reconstruites en TIFF 16 bits avec metadonnees suffisantes pour la suite du pipeline;
7. reporter la correction colorimetrique a une story ulterieure.

Pipeline post-MVP deja reserve par l'architecture:
1. acquisition scan en RVB la plus neutre possible;
2. neutralisation des automatismes scanner si possible;
3. detection ArUco sur l'image scannee;
4. redressement geometrique complet de la page;
5. extraction des patchs sur la page redressee;
6. calcul d'une correction couleur page-par-page;
7. application de la correction aux zones frame;
8. export des frames reconstruites en TIFF 16 bits;
9. conversion vers le format d'encodage uniquement a l'etape `encode`.

Approche de correction recommandee pour la story post-MVP:
- matrice 3x3 + courbes par canal, ou petite LUT 3D;
- preset de patchs connu et versionne;
- verification par mesures simples et comparaison visuelle.

> Note 2026-08-06 (story 4.8, valeurs theoriques — EPIC4-ARB-7). La table de
> valeurs theoriques existe: `patch_values.py`, **sRGB D65, entiers 8 bits par
> canal**, version `patch-values-1` (une seule table active, les anciennes
> conservees en lecture; toute modification de valeur = nouvelle version,
> jamais d'edition en place). 12 valeurs: axe neutre 6 niveaux (20..245 —
> jamais 0/0/0 ni 255/255/255, saturation d'encrage et papier nu non
> mesurables), 3 primaires et 3 secondaires desaturees pour rester dans le
> gamut d'une conversion CMJN non controlee. Le registre 4.7 reference des
> identifiants de valeurs, jamais des triplets (un test verrouille l'unicite
> du point de verite sur tout src/). Le flux couleur de bout en bout est
> documente maillon par maillon avec ses pertes dans le docstring du module
> (valeurs -> reportlab RGB device sans ICC -> pilote CMJN non controle ->
> papier -> scanner RVB automatismes non controles -> lecture sur page
> redressee 5.4), ainsi que les preconditions de la future LUT
> (`LUT_PRECONDITIONS`, chacune avec son garant) et les hypotheses materiel
> bloquantes (scanner a plat, DPI >= seuil QR, automatismes desactives si
> possible). L'espace des patchs ne se confond jamais avec
> `target_colorspace` (cible de reconstruction du rush). Differes a 5.4,
> nommes sans etre implementes: conversion active, ICC, linearisation,
> DeltaE, mesure spectrale (decision 3 du 2026-08-02, non preemptee).

> Note 2026-08-07 (Epic 5, EPIC5-ARB-2 et EPIC5-ARB-3 — voir
> `decisions-2026-08-07-epic-5.md`). **La pipeline post-MVP ci-dessus est
> incomplete: elle ne dit rien du gamut, et telle quelle elle perd le contenu
> sature.** Constat mesure sur planche reelle: un pilote CMJN non controle
> **ecrete**, c'est-a-dire applique plusieurs valeurs sources sur la meme
> encre; aucune LUT n'inverse une application plusieurs-vers-un. L'information
> saturee est donc detruite **a l'impression**, en amont de toute
> calibration — et les patchs actuels, tous a l'interieur du gamut, sont par
> construction incapables de mesurer cet ecretage (17,8 % du cube RGB couvert
> par l'enveloppe des 12 patchs; 63,3 % des pixels utiles de la mire de test
> hors de cette enveloppe).
>
> Deux etapes s'inserent donc dans la pipeline post-MVP:
>
> * **entre 1 et 2 (cote impression)**: une **compression de gamut `G`**,
>   monotone, injective, versionnee, appliquee aux **zones frame uniquement**
>   — jamais aux patchs, qui sont la reference de la correction. Une
>   compression strictement monotone est un-vers-un, donc reversible, la ou un
>   ecretage ne l'est pas.
> * **entre 7 et 8 (cote scan)**: l'**expansion `G^-1`**, appliquee
>   **imperativement apres** la correction `C` issue des patchs. `C` corrige une
>   distorsion physique mesuree, `G^-1` inverse une transformation numerique
>   deliberee: inverser l'ordre amplifierait l'erreur non corrigee d'impression
>   et de scan par le gain de l'expansion.
>
> `gamut_map_id` entre au payload QR (story 5.9) pour qu'une planche reste
> inversible sur une autre machine (verifie: 427 octets sur un budget nominal
> de 512). L'identite `gamut-map-none-1` reste une valeur valide de premier
> rang. Cout a dimensionner par la story, chiffre et non estime: comprimer
> d'un facteur `k` amplifie au retour le bruit scanner et la quantification
> par `1/k`. **Precondition bloquante**: le chemin scan doit d'abord redevenir
> 16 bits de bout en bout (`extract_scan_frames` ecrit du PNG 8 bits,
> `cli.py:263` lit sans `IMREAD_UNCHANGED` — findings differes de 5.5, repris
> par la story 5.0), sans quoi l'expansion amplifie une quantification 8 bits
> en bandes visibles. Des **patchs sentinelles** hors gamut, en echelles de
> saturation et exclus du jeu d'ajustement de la LUT (story 5.9), mesurent la
> frontiere reelle du gamut imprime et dimensionnent `G`.

> Note 2026-08-08 (story 5.10, `G` **livree** cote impression): la compression
> de gamut cesse d'etre une etape de pipeline decrite pour devenir un registre
> versionne, `src/mixed_media_utility/gamut_map.py`, applique au **seul** point
> ou des pixels de frame entrent dans le PDF
> (`pdf_render.load_frame_image_for_print`). Ce qui est livre est le
> **mecanisme**, pas le dimensionnement.
>
> Forme retenue au MVP -- `gamut-map-lin-1`, **affine par canal**, identique
> sur R, G et B: `G(x) = 0,06 + 0,88 x` sur le domaine normalise, inverse
> analytique exact `G^-1(y) = (y - 0,06) / 0,88`. Cout **mesure**, pas estime:
> `1/k = 1,136` (+13,6 % de bruit et de quantification au retour); erreur
> d'aller-retour sur la grille 8 bits `0,5/k = 0,568` code, donc **1 code**
> apres re-arrondi; plage de sortie 15..240, soit 226 codes distincts sur 256
> et **30 codes (11,7 %) en collision**. Aller-retour mathematique exact a
> 2,2e-16 sur 65 536 echantillons.
>
> **Limite a ne pas perdre de vue**: une compression affine par canal ne traite
> **pas** l'ecretage de chrominance. `(255, 0, 0)` devient `(240, 15, 15)`,
> toujours tres au-dela du gamut CMJN atteignable, et le constat mesure
> ci-dessus (63,3 % des pixels utiles hors enveloppe) n'est donc pas resorbe.
> Une compression dirigee vers la frontiere du gamut suppose de connaitre cette
> frontiere: c'est le mandat des sentinelles de 5.9, et a **2 echelons par axe**
> (EPIC5-ARB-17b) elles **detectent** un ecretage sans le localiser assez
> finement pour dimensionner `G`. Le MVP livre donc un `G` fixe et une
> instrumentation qui dit *s'il y a* ecretage, pas *ou* il commence.
>
> **Le defaut reste l'identite** (EPIC5-ARB-15): la moitie « decomprimer »
> vit dans la story 5.4b, post-MVP, et un defaut comprimant ferait imprimer,
> scanner et exporter des frames que rien ne decomprime -- visiblement
> delavees, sans qu'aucune etape n'echoue. La compression reelle s'active
> explicitement, `--gamut-map gamut-map-lin-1`, ce qui veut dire que la
> premiere planche de caracterisation doit etre **tiree avec l'option**.
>
> Deux regles de quantification, asymetrie assumee: la troncature `>> 8`
> d'origine est conservee **bit pour bit** sur le chemin identite -- c'est
> l'ancrage de non-regression d'une restructuration qui touche le seul chemin
> de pixels du PDF -- et l'arrondi est au plus proche sur le chemin comprime,
> ou une troncature ajouterait un demi-code de biais que `1/k` amplifierait.

> Note 2026-08-07 (EPIC5-ARB-14, **amendement d'un arbitrage Epic 4 clos**):
> le plafond de pastilles par page passe de **24 a 36**
> (`patch_presets.MAX_PATCHES_PER_PAGE`). Le chiffre est **mesure**, pas
> choisi: c'est la capacite geometrique minimale des deux orientations
> (portrait 4 colonnes x 12 rangs = 48; paysage 6 colonnes x 6 rangs = 36) une
> fois que le bloc de pastilles repose sa geometrie de colonnes dans les
> bandes laterales deja libres. Il tombe juste: 12 valeurs d'ajustement en
> repetition 2 (24) + 6 sentinelles en repetition 2 (12) = 36, donc la
> repetition >= 2 d'EPIC4-ARB-6 est preservee **y compris pour les
> sentinelles** — sans quoi une sentinelle isolee confondrait « ecretee » et
> « mal imprimee ». **Rien d'autre ne bouge**: `page_templates.py` et
> `layout.py` sont intacts (zones de frames, marqueurs ArUco et QR inchanges
> sur les 33 gabarits, EPIC5-ARB-1 reste valide), `patches-9-v1` et
> `patches-12-v1` conservent exactement leurs placements, et
> `DEFAULT_PATCH_PRESET` ne change pas. Seul le **nouveau preset sentinelle**
> pose une geometrie de colonnes propre, ce qu'autorise le placement par
> couple `(template_id, preset_id)`.

Important:
- le print-scan est une nouvelle acquisition calibree;
- le MVP cherche une reconstruction geometrique fiable et une sortie normalisee, pas une equivalence colorimetrique absolue;
- les metadonnees necessaires a la future correction doivent deja exister dans le manifest et le QR quand elles sont critiques;
- une perte colorimetrique est **declaree** (manifest, indicateur d'ecretage), jamais subie silencieusement.

### Note du 2026-08-08 (story 5.9): patchs sentinelles et aller-retour de gamut

La table de valeurs active est `patch-values-2` (EPIC5-ARB-21). Elle porte 18
valeurs: 10 d'ajustement et 8 **sentinelles de gamut** (role
`gamut_sentinel`), imprimees hors du gamut CMJN atteignable pour mesurer la
frontiere reelle et detecter un ecretage planche par planche. La v1 reste
enregistree et resolvable; `patches-9-v1` et `patches-12-v1` continuent de la
referencer et d'imprimer ses valeurs.

Trois consequences a connaitre avant de lire le reste de cette section:

1. **Les sentinelles ne peuvent pas atteindre le jeu d'ajustement.**
   `PatchValuesTable.adjustment_values()` les exclut par construction et
   `ensure_no_sentinel_in_adjustment_set()` refuse toute sentinelle presentee
   comme telle. Un point ecrete par construction, injecte dans l'ajustement,
   tirerait toute la LUT -- et le symptome serait une correction plausible,
   pas une erreur.
2. **La protection contre la bave d'encre a change de nature**
   (EPIC5-ARB-17(a)): la regle de disposition « aucune paire de pastilles
   saturees adjacentes » est remplacee par une garantie geometrique
   d'echantillonnage (`SAMPLING_INSET_MM = 3.0`, `SAMPLED_SIDE_MM = 6.0`),
   verifiee sur les 99 couples du registre. La story de calibration doit
   echantillonner ce carre-la, et pas les 12 mm entiers.
3. **`gamut_map_id` est un champ obligatoire du payload QR** (EPIC5-ARB-13),
   sans bump de `schema_version` et sans branche « champ absent ». Il coute
   34 octets avec l'identite `gamut-map-none-1`, ce qui fait passer le repere
   de capacite nominale de 5 a 4 slots par page et bascule la geometrie QR en
   `degraded` a 8 slots (symbole agrandi a 35,56 mm, emprise 38,27 mm, qui
   tient dans la zone reservee de 40 mm).

### Note du 2026-08-08 (story 5.4a): le Gate 4 couleur est ferme

Quatre axes restaient ouverts depuis la revue de la story 5.5 (« 5.5 ne
debloque pas 5.4 en l'etat »): **ordre exact des conversions**, **gamma /
fonction de transfert de travail**, **forme de la correction**, **precision de
travail** — plus la **metrique d'acceptation** exigee par `TEST_PLAN.md:211`.
Ils sont tranches par **EPIC5-ARB-24 a EPIC5-ARB-28**
(`decisions-2026-08-08-epic-5.md`), qui portent aussi le verdict axe par axe du
Gate 4 et le statut des huit preconditions de `patch_values.LUT_PRECONDITIONS`.
Les deux axes voisins ne sont **pas** rouverts ici, seulement cites: le
**gamut** (EPIC5-ARB-2 / EPIC5-ARB-3, et `G` livree par 5.10) et l'**ICC**
(EPIC5-ARB-6: pas de profil ICC au MVP, les tags du conteneur final etant poses
par 6.3).

**Complete le meme jour par EPIC5-ARB-29 a 31**, apres la revue en trois
couches de la story 5.4a: trois points de la premiere redaction n'etaient pas
implementables en l'etat, et les corriger changeait le **contenu** des
decisions, donc de nouvelles entrees numerotees plutot qu'une reecriture en
place. **ARB-29** definit le jeu d'ajustement et le jeu de sentinelles **par
role et par preset**, jamais par enumeration litterale d'identifiants -- le
defaut de la CLI est `patches-12-v1` sur `patch-values-1` (12 valeurs
d'ajustement dont 6 neutres), et `patches-9-v1` n'en imprime que 9 sur les 12
de sa table. **ARB-30** ajoute le **branchement** que la sequence n'avait pas
(la decision `applied` / `failed` tombe a l'etape 10, apres l'application de
`C`), scinde l'etape 12 en quantification puis ecriture, et tranche le sort
d'une valeur sortie de [0, 1] par `G^-1`. **ARB-31** pose la **ponderation** de
l'ajustement, que « moindres carres » laissait implicite.

**La pipeline post-MVP en 9 etapes ci-dessus reste vraie mais n'est pas
executable telle quelle**: elle ne dit ni ou l'on linearise, ni ou l'ordre des
canaux change, ni dans quel domaine `G^-1` s'applique. Sequence complete,
cote scan, du fichier scanne a la frame exportee (EPIC5-ARB-24):

1. lecture native `IMREAD_UNCHANGED`, ordre **BGR**, rien de colorimetrique;
2. redressement geometrique (homographie des 4 coins); **tout ce qui suit lit
   la page redressee**;
3. lecture du QR: `template_id`, `patch_preset_id`, `target_colorspace`,
   `gamut_map_id` — quatre entrees, aucune devinee;
4. echantillonnage des pastilles sur le carre `SAMPLED_SIDE_MM`, en **deux jeux
   disjoints des la source** (`adjustment_values()` / `sentinel_values()`), le
   jeu d'ajustement de la page etant l'intersection avec `preset.value_ids`
   (EPIC5-ARB-29);
5. **point unique de changement d'ordre de canaux**: les references
   (`PatchValue.rgb`, RGB) sont reordonnees en BGR **ici et nulle part
   ailleurs**. Le raster n'est jamais reordonne;
6. promotion du raster en `float64` et normalisation [0, 1] (l'agregation des
   pastilles est deja en float64, H5(iii));
7. **point unique de linearisation de la chaine de correction**: EOTF sRGB
   (IEC 61966-2-1), sur les mesures, les references **et les zones frame** —
   les trois cotes, ou aucun. La metrique linearise **une seconde fois**, en
   interne, et c'est assume: elle contracte des valeurs reencodees a l'etape 9;
8. ajustement pondere (EPIC5-ARB-31) puis application de la correction `C`, en
   lineaire; **le raster non corrige est conserve**;
9. **point unique de de-linearisation**: OETF sRGB, retour au domaine encode;
10. metrique d'acceptation sur les pastilles corrigees (jamais comprimees, donc
    jamais expansees) et verdict d'ecretage des sentinelles, **independant** du
    statut (EPIC5-ARB-16). **C'est le rang de la decision `applied` / `failed`**:
    en `applied` le raster corrige poursuit, en `failed` c'est le raster non
    corrige (EPIC5-ARB-30);
11. **`G^-1`**, resolue depuis `gamut_map_id`: **apres `C`** (invariant 1
    d'EPIC5-ARB-2), **dans le domaine encode**, sur les **seules zones frame**,
    et **dans les deux branches** — `G` a ete appliquee a l'impression
    independamment de `C`;
12. **quantification puis ecriture, deux operations distinctes** (EPIC5-ARB-30):
    **12a** ecretage a [0, 1] puis `rint(x * 65535)` en `uint16` — c'est le
    **point unique de quantification**, et les pixels ecretes sont comptes et
    rapportes; **12b** ecriture TIFF 16 bits en BGR par `export_frame_tiff16`,
    qui **refuse les flottants** et ne quantifie rien;
13. le **retour vers l'espace cible** est **declare, pas calcule**:
    `target_colorspace` n'entre dans aucune des etapes 1 a 12, la conversion
    restant a l'etape `encode` (etape 9 de la pipeline post-MVP ci-dessus).

**Le point le moins intuitif, et le plus couteux a se tromper**: `G^-1`
s'applique dans le domaine **encode**, pas en lineaire. `G` opere sur des codes
normalises (`gamut_map.to_print_8bit`), et son inverse n'est exact que dans ce
domaine-la; le conjuguer par l'EOTF pour l'appliquer en lineaire respecterait
l'invariant 1 en cassant l'invariant 3 (injectivite utile seulement si
l'inverse est exact — aller-retour mesure a 2,2e-16). D'ou l'ordre 9 -> 11.

**Ce que les quatre axes disent, en une ligne chacun** (detail et alternatives
ecartees dans `decisions-2026-08-08-epic-5.md`):

* **Gamma** (EPIC5-ARB-25): `C` s'ajuste et s'applique en **lineaire sRGB**,
  reencodee avant `G^-1` et avant l'export. Les distorsions corrigees (densite
  d'encre, blanc du papier, exposition du scanner) sont affines dans la
  lumiere, pas dans les codes; ajuster en encode donnerait une correction juste
  au centre de l'echelle et fausse aux deux bouts. La valeur canonique reste le
  triplet entier 8 bits: la linearisation est une derivation a l'usage, la
  table n'est pas touchee.
* **Forme** (EPIC5-ARB-26): **affine par canal + matrice 3x3 a somme de lignes
  contrainte**, identifiee `color-correction-affine-matrix-1`; **pas de LUT
  3D**. Comptage refait le 2026-08-08, **par etage**, parce que les deux etages
  ne consomment pas les memes valeurs: l'etage A prend 6 parametres pour les
  seules valeurs d'axe neutre (12 contraintes sur `patch-values-2`), l'etage M
  prend 6 parametres pour les seules valeurs chromatiques (18 contraintes) —
  une matrice a lignes de somme 1 laisse tout triplet neutre invariant, donc
  les neutres ne contraignent pas M. Chaque etage reste sur-determine d'un
  facteur 2 a 3, il laisse donc un residu reel. La plus petite LUT 3D utile
  consommerait 24 parametres pour 30 contraintes brutes: son residu n'est pas
  nul par construction, mais son conditionnement mesure est de **98,8** contre
  **2,27** pour l'etage M — ses parametres seraient domines par le bruit de
  mesure, et la metrique deviendrait tautologique. Elle placerait en outre
  **ses 8 noeuds sur 8** hors de l'enveloppe mesuree (17,8 % du cube RVB: les
  8 sommets du cube ont leurs coordonnees dans {0, 255}, le jeu d'ajustement
  est borne a [20, 245] par canal). Le plafond de 36 pastilles la ferme
  structurellement: 18 valeurs par page au mieux.
* **Precision** (EPIC5-ARB-27): **`float64` de bout en bout**, importe de
  `gamut_map.WORKING_DTYPE` et jamais redeclare; aucun arrondi entre la
  promotion (etape 6) et l'etape 12a, qui est le **seul** point de
  quantification du chemin scan — symetrique de `to_print_8bit` cote
  impression. Les references restent 8 bits exactes, jamais requantifiees, et
  `source_bit_depth` est capture a l'etape 1 puis **transporte**, jamais deduit
  du dtype remis a l'export.
* **Metrique** (EPIC5-ARB-28): critere `delta_e76_srgb_d65` (CIE76 sous
  l'hypothese sRGB D65 **declaree par la table, non garantie par le scanner**),
  agrege en moyenne et maximum sur le jeu d'ajustement; seuils de l'entree
  versionnee `color-acceptance-1`: **moyenne <= 8,0 et maximum <= 16,0**, les
  deux requis. Diagnostic distinct et sans seuil: `channel_relative_deviation`.
  **Les deux nombres sont poses, pas mesures**; ils se revisent par une
  nouvelle entree `color-acceptance-<n>`, jamais par edition en place — meme
  motif que le registre de `gamut_map` et la table de `patch_values`.

**Ce que la metrique ne mesure pas, a citer partout ou le chiffre est cite**:
elle n'est pas une mesure colorimetrique (aucune mesure spectrale n'existe dans
le projet), elle ne dit rien de l'ecretage (c'est le role des sentinelles, et
les deux verdicts restent independants), elle ne dit rien des pixels hors de
l'enveloppe des pastilles, elle a un plancher de bruit — a
`source_bit_depth = 8`, un code vaut `dE76 ~ 0,3` a `0,5`, amplifie par 1,136 a
l'expansion, d'ou l'interdiction de declarer un seuil sous 1,0 —, elle est
**in-sample** (calculee sur les valeurs memes qui ont servi a ajuster `C`, donc
un residu d'ajustement et non une mesure de generalisation), et elle suppose le
raster redresse a au moins `QR_MIN_SCAN_DPI` — ce qui n'est pas garanti, le
`dpi` etant un parametre **declare** dont depend le cardinal de pixels de H3.

**Statut du gate**: **PASS**, confirme apres la revue en trois couches du
2026-08-08. La calibration n'est plus « conceptuelle ou contradictoire ». Trois
residus sont **declares**, non caches: le seuil est pose et non calibre
(premier pilote papier), aucune mesure spectrale n'est disponible, et aucune
fixture du depot ne peut aujourd'hui reveler R9 — la **mire de degrades** du
`TEST_PLAN.md:258-272` est une preuve de mesure **posterieure** au gate, qui
servira a calibrer les seuils poses ici, pas une condition de sa fermeture.
L'implementation active reste post-MVP (story 5.4b).

> Note 2026-08-13 (`EPIC5-ARB-65`, story 5.19). La phrase « l'implementation
> active reste post-MVP (story 5.4b) » ci-dessus etait vraie jusqu'au
> 2026-08-12: `EPIC5-ARB-5` classait la calibration active en post-MVP, sans
> appelant sur le chemin de scan. `EPIC5-ARB-65` renverse cet arbitrage, et la
> story 5.19 (et non 5.4b, scindee et absorbee depuis dans les stories 5.16 a
> 5.19 de l'Epic 5) cable l'application: `scan_command` ajuste une correction
> sur la page de calibration du lot et l'applique aux pixels des planches
> avant leur ecriture. Le pipeline en 9 etapes decrit plus haut reste la
> pipeline **retenue** au sens du mecanisme; il n'est plus « post-MVP » au
> sens de son execution. Detail: `decisions-2026-08-11-epic-5.md`,
> `EPIC5-ARB-65` et `EPIC5-ARB-68` a `EPIC5-ARB-71`.


## 9. Positionnement des EPICs 2 a 6

### Epic 2
- contrat manifest v2;
- conventions de nommage;
- payload QR;
- arborescence reconstructible;
- logique de creation/reconstruction locale.

### Epic 3
- extraction deterministe des frames;
- persistance des metadonnees source utiles au manifest.

### Epic 4
- generation du PDF comme support auto-descriptif;
- layout stable;
- QR de page;
- marqueurs ArUco;
- preset de patchs versionne.

### Epic 5
- ingestion scan;
- detection geometrique;
- calibration couleur page;
- extraction des frames rescanees;
- regeneration ou enrichissement du manifest local.

### Epic 6
- reconstruction video;
- publication dans un codec cible;
- reinjection des seules metadonnees techniques realistement supportees.

## 10. Priorisation et parallelisation

Ordre recommande:
1. Epic 2
2. Epic 3 et Epic 4 en parallele
3. Epic 5
4. Epic 6

Parallelisation autorisee:
- spike QR et layout pendant la finalisation de l'Epic 2;
- spike codec / conteneur / metadonnees pendant la finalisation de l'Epic 2;
- implementation `extract` et `makepdf` apres gel du contrat;
- sous-tracks geometrique et couleur dans l'Epic 5 apres gel du template PDF.

Condition de passage:
- aucun travail de production sur `scan` ou `encode` ne doit etre considere stable tant que la matrice de responsabilite des metadonnees et le contrat minimal de reconstruction ne sont pas valides.

## 11. Metadonnees video finales

Position retenue:
- le conteneur video final ne remplace pas le manifest;
- il porte uniquement des metadonnees techniques de publication ou de decodage;
- il faut privilegier un master mezzanine robuste, type ProRes MOV ou DNxHR MOV/MXF selon la cible;
- les exports H.264 / H.265 doivent etre traites comme derives de diffusion.

Metadonnees realistement preservables ou reinjectables selon les codecs cibles:
- resolution;
- cadence;
- time base;
- pixel format;
- color primaries;
- transfer characteristics;
- colorspace;
- certains champs de timecode selon conteneur.

Metadonnees a conserver hors conteneur, dans le manifest:
- informations de calibration;
- provenance scan;
- mapping complet page / slot / timecode;
- checksums;
- historique local de reconstruction.

> Note 2026-07-21 (stories 4.3/4.6/5.5/6.2/6.3): confirme par essais reels ffmpeg 6.1.1 + ffprobe (story 6.3). Pour une reinjection fiable des 3 champs couleur (color primaries, transfer characteristics, colorspace), les 3 flags ffmpeg `-colorspace`, `-color_primaries`, `-color_trc` doivent etre poses ensemble — specifiquement necessaire pour ProRes/MOV (un seul flag laisse les 3 champs `unknown` cote ffprobe, et ffprobe omet silencieusement les champs "unknown" en sortie JSON). Le timecode `tmcd` est confirme fiable sur les masters MOV (ProRes, DNxHR): convention eprouvee en post-production (Premiere/Resolve/Avid). Sur les derives de diffusion MP4 (H264/H265), ffmpeg lit/ecrit reellement un flux `tmcd`, mais ce support reste classe "best effort" (non garanti chez les outils tiers), par prudence produit.

> **Note 2026-08-10 (story 6.0) — taguer n'est pas convertir, et c'est la
> distinction la plus couteuse de cette section.** Les trois flags ci-dessus
> **decrivent** le flux; ils ne pilotent pas la matrice RVB -> YUV de swscale,
> qui reste a son defaut **BT.601**. Un master pouvait donc etre converti en
> BT.601 tout en se declarant BT.709, et le fichier etant **auto-coherent**,
> l'ecart etait indetectable en aval.
>
> Mesure, aller-retour par la commande de production, remesuree trois fois de
> facon independante: **erreur max 40,33/255** sur les couleurs saturees (vert
> 40,33, magenta 39,35, cyan 25,57), et **0,11 sur le blanc, 0,12 sur le
> gris 50 %** — les neutres sont **inchanges** par le correctif. La derive etait
> donc invisible sur l'axe neutre, c'est-a-dire invisible pour tout test ecrit
> spontanement. Avec la matrice posee explicitement
> (`-vf scale=out_color_matrix=<matrice du profil>:out_range=tv`): **1,06/255**.
>
> Les deux gestes sont **necessaires et independants**: le filtre **sans** les
> trois tags donne `color_space=unknown` et un ecart de **23,00/255**.
>
> > **RENVERSE le 2026-09-07** par le lot de tagage colorimetrique
> > (`3ff23d6f5`), et signale par la couche 3 de sa revue -- ce module
> > s'adossant explicitement a la section 11 de ce document, le laisser dire
> > l'inverse de ce qu'il produit n'est pas une coquette de documentation.
> >
> > La chaine **tague desormais par elle-meme** : `build_setparams_link` pose
> > les proprietes sur la **frame**, donc « le filtre sans les trois tags »
> > rend maintenant `color_space=bt709` et un ecart **inferieur a 2/255**, non
> > plus `unknown` et 23,00. Le banc qui portait ce fait
> > (`test_codec_profiles.py::filtre_sans_tags`) a ete retourne plutot que
> > retire, en le disant sur place.
> >
> > **Ce qui reste vrai, et c'est l'essentiel de la phrase d'origine** : taguer
> > n'est pas convertir. Le cas discriminant est desormais `sans_filtre`, qui
> > rend toujours plus de 20/255 -- sans le filtre, la matrice n'est pas posee,
> > et aucun tag ne repare une conversion qui n'a pas eu lieu.
> >
> > **Pourquoi le fait a change** : entre ffmpeg 6 et 8, `-color_primaries` et
> > `-color_trc` cessent d'atteindre l'encodeur (mesure sous un build n8.1.2).
> > Seule la propriete portee par la frame compte, ce que `setparams` pose --
> > d'ou un maillon qui tague sans qu'on ait a le doubler d'options CLI.
>
> Consequence pour l'Epic 6: la chaine de scan mesure un dE76 moyen de 6,56
> (`analyse-2026-08-10-mesure-de76-scans-reels.md`); un encodage qui
> reintroduit 40/255 annule ce que cinq stories de l'Epic 5 ont instrumente.
>
> Deux limites nommees, non corrigees: les trois profils **ProRes n'emettent
> aucun `color_range`** la ou DNxHR/H264/HEVC emettent `tv` — forcer
> `-color_range` sur ProRes demande une validation NLE reelle avant d'etre
> promis; et le vocabulaire de matrices reellement utilisable de bout en bout
> est **`{bt709, smpte170m, smpte240m}`**, le filtre `scale` acceptant a lui
> seul n'importe quelle valeur (15 candidats sondes, tous `rc=0`) alors que les
> trois options de tag en refusent la majorite.

## 12. Decisions fermees pour lancer le dev

1. Format maitre de sortie: ProRes MOV par defaut, precisement ProRes 422 HQ (profil `prores_hq`).
2. Contrat d'acquisition scan MVP: tous les formats de scan lisibles sont acceptes en entree; la sortie reconstruite est normalisee en TIFF 16 bits.
3. Niveau d'ambition couleur du MVP: pas de correction colorimetrique active dans cette iteration; uniquement geometrie, reconstruction et preservation des metadonnees utiles. **Renverse par `EPIC5-ARB-65` le 2026-08-12** (voir la note du 2026-08-13 section 8): la story 5.19 applique desormais une correction active aux pixels du chemin de scan.
4. Mode d'encode en absence du rush source: encode autorise a partir des seules frames rescanees et des metadonnees manifest/QR.
5. Contraintes de lisibilite terrain: hypotheses provisoires deja posees; validation empirique attendue via une story de faisabilite immediate.

> Note 2026-07-21 (stories 4.3/4.6/5.5/6.2/6.3): DNxHR HQ est confirme comme un profil 8 bits 4:2:2 (`yuv422p`) uniquement — le pix_fmt 10 bits (`yuv422p10le`) est refuse par ffmpeg pour ce profil et n'existe que sur les tiers HQX/444 (bug reel trouve et corrige en story 6.2, confirme comme contrainte de specification Avid par un second avis technique independant). Un profil `dnxhr_hqx` a ete ajoute au catalogue pour couvrir ce besoin 10 bits sans risque de regression. Ces confirmations codec/metadonnees s'appuient sur des essais REELS (ffmpeg/ffprobe local, version 6.1.1); les confirmations QR/ArUco des sections 6 et 7 s'appuient sur des essais SYNTHETIQUES (OpenCV) et restent a valider par un vrai pilote d'impression/scan avant fermeture definitive.

## 13. Conclusion operable

Le point le plus important a traiter maintenant reste Epic 2. La pipeline couleur MVP n'est plus bloquante car son ambition a ete reduite a un mode no-op explicite. Les spikes encore utiles portent surtout sur la lisibilite QR terrain, les seuils ArUco et la matrice finale de metadonnees video d'encodage.