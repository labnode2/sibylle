"""Words of Wordle: five letters from a to z, lower case, no accent.

They come from a file of the words of Lexique 3.83 in tiers of frequency, `wordle-fr.json`,
which the worker fetches each night (services/wordle_lists.py); `lists_from` checks a version
before the game may use it. Its `answers` are the words of the day, in tiers from the most common
to the rarest, each tier `{id, min, max, count, words}` and each word `{word, spelling, freq,
kind}`; its `guesses` are every word a try may be, the answers among them.

`ANSWERS` and `ACCEPTED`, written by hand before that file, stay for a server that has never
fetched it, and for the word every newsroom shared before each had its own (`wordle_answer`):
`EXTRA` are further words accepted as a try (conjugated forms, plurals, rarer words) that never
come up as an answer. Order of `ANSWERS` is kept: that word is picked by an index into it, so
only append to it.
"""

import json
import re
from dataclasses import dataclass
from typing import Any, TypeGuard

_ANSWERS = """
abris acier adieu agent aigle ailes aimer album algue allee amour ananas angle animal annee
arbre argent arret astre atout avion avril bague balai balle banane barbe barque bassin bateau
beige billet blanc blason bocal boire boule bravo brume bruit cadre calme canal
carte casse cause cedre chaos chant chaud chene chevre chien chute cible ciel cigale cirque
citron clair classe coeur colle copie corde corps coude coupe cours crabe craie crane
creme crise croix cuire cuisse danse debut dense dette doigt douce drame droit dunes eaux
echec ecole ecran effet eleve email encre envie epice epine equipe erable espoir essai etage
etang etoile fable facon faire fange farce fauve femme fente ferme fetes fiche fleur foire
folie fonds force forge forme fouet foule frais frere fruit fumee furet galet gants garde
gateau gaufre genou geste givre glace globe gorge gout grain grand grave greve grotte guide
habit haies herbe heure hibou hiver homme hotel huile humer ideal image ivoire jambe jardin
jaune jeudi jeune joint jolie joues jouer juger jumeau jupes jurer juste kiosque
laine lampe lance large lavis leger lente lettre levre liane libre ligne limon
linge litre livre local loger loisir loupe lourd lueur lundi lutte magie maire maison
marche marin masse matin melon menthe merci metal metro miche miel miroir mode
moine monde monte morte motif moule moyen mulet mur muser nacre nager neige neuf noble
noces noeud noire noix nuage nuire nuits ocean odeur oeufs ombre onde opera orage ordre
oreille orgue otage ouate outil ovale pacte page paire palme panne papier parce parti
passe pates patte pause peche peine perle peser petit phare piano piece pilot pinte pique
piste place plage plaie plain plan plein pluie plume poche poele poing point poire poivre
polar pomme ponts porte poser poule pouls prise prix prune puits quand quart queue quiz
radis rafale rampe rapide rayon recit reine rejet rente repas reste revue rhume rider rieur
rives robot roche rondes rouge route ruban ruine ruses sable sabot sacre sages saine
salle salon sauce saute savon scene seche selle serre seuil siege signe silex singe
sirop soeur soldat solde somme songe sorte souci soupe source stade stage store stylo sucre
suite sujet table tache taire talon tapis tarte tasse taupe temps tente terre tetes
texte tigre timbre tirer titre toile toits tombe tonne torse touche tours trace train
trait tuile tulipe usine vache vague valet valse vapeur veine velos vente verbe verre
verte veste vieux vigne ville viser vitre vivre voile voire volee votre vrai 
zebre zeste zones
""".split()

_EXTRA = """
abats abeille abime abord abuse acces accord acide actes actif adage adore adulte affut
agace agile agite aider aiguille aille aimee aises ajout alarme alibi allez allie allure
alors amant ample ampli amuse ancre anges angles anime annex anode apres arene arche ardu
arome array arrive asile atome attrape aubes aucun audit aurai autre aval avant avare avide
avoir avons axiome azote bacon badge bagne bains baisse balle bambou bande banal banc barre
bases basse baume beau bebes bemol benne berge besoin beton beurre bible bilan billes biner
bison blague blesse bleue bloc blond bloom boeuf boite bombe bonne bonus bords borne bosse
botte bouche boucle bouge boues boule bouts bovin boxer brabant braise brame branche brasse
brave brebis breve brief brique brise broche broder bronze brosse bruler brute budget buffle
buisson bulle bureau butin cabane cabine cable cache cacao cadet cadeau cages caisse calcul
calot camp canif canon cantal caper capot carat carpe carre cases cause cave ceder celle
cendre cense cerf cerne cesse chair chaise chale champ chance chaque charge chasse chats
chaux chef chemin cheque cher chiot choc choix chose cidre cimes cinq circa clans clef
clore clous cloue cobra cocon coder coffre coins colis colon comme conte copin coque corne
cotes coton coucou couds couler coups cour court cousin couvre crains cran crash crier
crime crins cris croit crown cruel cubes cuill cuite cycle dague dames darne dater dauphin
debat decor defi degat degre dehors delai demain demon dents depart depot desir dette deuil
devoir dicton dieux digne dingue disco dites divan docte dogme dolce domus donne dorer dorme
dotee douze draps drone dupe durer eblouir ebene echos eclat edite effort egale egout elans
elite elles emane emeri emois emmene empan encas endos enfin enjeu ennui entre enver envoi
epais epave epees epoux epure erige errer escale espace esprit essor estime etude evier
evite exact exces exode extra fades faims faite falot fanes farci fatal faute faune faveur
feraille ferre ferry festin feuille fiers fievre fifre filet filin films final finir fiole
fiscal flair flamme flan flaque fleuve flore flots fluide flute foins foins folle fonce
fonte forat forer forme forte fosse foudre fourmi fraise franc frein frime frire frite
front frotte fugue fuite fumer fusee fusil gaffe gagne gains galop gamme garce gares gaule
gazon geant gelee gemme genre gente gerbe gibier gifle gilet gland glisse gluant gomme
gonfle gosse goute grace grade grele grille grise gros groupe gruau guepe guerre guets
gueule gui hache haine halle halte hamac hanche hardi harpe hasard hater haute havre hello
heros heure hirsute hobby hotes houle huits humus hurle hymne iconic idees igloo ilots
images immun impot index infos inlet inox instar ironie issue ivres jadis jambon jante
jarre jeter jeton jeux joies jours joyau jugee juive jument jures jusqu kebab kilos label
laces laids laine laits lames lamper lancer langue lapin laps larme larve laser lassi laver
lecon legal legue lents lequel lever lezard liens lieux lilas limes lions lisse listes
livre loche loges loin lotus louer loups lover loyer lucky lunes lutin luxes macon mages
maigre mains maint mairie maitre major malle mamie manche manga manie manoir marge marie
marre marteau masque match mater maudit mauve mazout meche medal meler membre meme mener
menu merle mesure meteo metre meuble miens mieux mille mimer minaud minci mines mirer
missile mitan mites mixte modes moins moisi molle monte moral morse mortel motos motte
mouche mouton muets multi muret museau musee mythe nager naif nappe natte naval navet
neons nerfs net neveu niche nid niveau nobles noces nodal noeuds nomme nonne norme notes
notre nouer nuque oasis objet obtus ocres offre oiseau olive ombre ondee opale optez
orbite ordre oser ours outre ovnis ozone pagne paien pains paisible palais pale palet
panel panier pantin paons papa parfum parole part patin patio paume pavot payer pays peaux
pedal peigne peint pelle pente pepin percer perdu peres perte pesee peste petal peuple
peur piano picot pieds pieux pigeon pile pilon pinson pion pipe pitre pivot pizza plaid
plaine planche plat plomb plonge plots plus poids poils poing poker polie ponte porc port
poste potin pouce poudre pouce pour pousse prado pre prefet preuve prier primo propre
prune pubis puces puis pulls punch pure putsch puzzle quasi quels quete quill quitte
quota rabot racer radar radio rage raide rails raison ramer rando rapt rares rasoir ratio
rayer reçu reels regle regne rein relais remue rendu renne repli requin reseau retro
reves rhone riche rides rimer rire rival rixes robes rocks roman ronde rosee rouet
roule royal rubis rudes rural rusee sabre sacre safran sagas saint saisi salut sapin
satin sauna saura savoir scoop sceau seaux sedan sein selon semer sens sept serie serpent
servi sexes shoot short siens sieste signal silos simple sinon sitot skier slips smash
snack sobre socle soeurs soie soins solde solos sombre sommet sonde sonne sorti soudain
souple sourd sous spore sport stars stock stoppe stupide style suave subir sucer sueur
suger sultan supin surfe sur surgi sushi tabac tables tache taille talus tango tante
tapas tarif tarot taxer taxis teint tempo tendu tenir tenue terme tests thems thon
tiede tiens timide tiree tisane tissu titan toast tolet tomate tonte topaz toque torche
total touer tousse tracer trame tramway tranche trefle treize tremble trente tribu
trier trois trone trop troupe trouve truc truite tubes tuer tunnel turbo tutu tuyau
types ultra union unite urgent usage usees usure utile vaste veaux vedet velo vendre
venin venir vents verger verifie vernis vers vertu vexer vices vides vilain vingt
viral virer visage vital vitre vivre vocal voeux voies voila voisin voler volet volt
votes voute voyou vulgaire wifi yaourt yeux zones zeros zinc zozo
""".split()


def _five(words: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for word in words:
        if len(word) == 5 and word.isascii() and word.isalpha() and word.islower():
            seen.setdefault(word)
    return list(seen)


# The answers, unique, in their order; nothing but five-letter words.
ANSWERS: tuple[str, ...] = tuple(_five(_ANSWERS))
# Whatever may be tried: the answers and the other words.
ACCEPTED: frozenset[str] = frozenset(ANSWERS) | frozenset(_five(_EXTRA))


# The word file

# What a version holds at least, and the most tiers it may have: a word's level is the rank of
# its tier, from 1 to 6, and the game shows a square per level.
MIN_ANSWERS = 100
MIN_GUESSES = 1_000
MAX_TIERS = 6
_WORD = re.compile(r"[a-z]{5}")
_TIER_KEYS = frozenset({"id", "min", "max", "count", "words"})
_WORD_KEYS = frozenset({"word", "spelling", "freq", "kind"})


class InvalidLists(ValueError):
    """A file the game cannot use; the message says what is wrong."""


@dataclass(frozen=True)
class WordLists:
    """A version of the words: the answers in tiers, from the most common to the rarest, and
    every word a try may be. `levelled` is false for the lists written by hand, one tier of their
    own: their words have no level."""

    tiers: tuple[tuple[str, ...], ...]
    guesses: frozenset[str]
    levelled: bool = True


# The lists written by hand, for a server that has not fetched the file yet.
OLD_LISTS = WordLists((ANSWERS,), ACCEPTED, levelled=False)


def decode(raw: bytes | str) -> dict[str, Any]:
    """The file's JSON object; InvalidLists when it is not one."""
    try:
        data = json.loads(raw)
    except (ValueError, RecursionError) as error:
        raise InvalidLists(f"not JSON: {error}") from error
    if not isinstance(data, dict):
        raise InvalidLists("not a JSON object")
    return data


def parse_lists(raw: bytes | str) -> WordLists:
    """The version a file holds, once checked (`lists_from`)."""
    return lists_from(decode(raw))


def lists_from(data: object) -> WordLists:
    """The version a decoded file holds, once checked: the format above, every word five
    letters from a to z, each answer once and among the guesses, at least 100 answers and 1 000
    guesses, 6 tiers at most. Raises InvalidLists, which says what is wrong."""
    if not isinstance(data, dict):
        raise InvalidLists("not a JSON object")
    answers, guesses = data.get("answers"), data.get("guesses")
    if not isinstance(answers, list) or not answers:
        raise InvalidLists("answers: not a list of tiers")
    if len(answers) > MAX_TIERS:
        raise InvalidLists(f"answers: {len(answers)} tiers, {MAX_TIERS} at most")
    if not isinstance(guesses, list):
        raise InvalidLists("guesses: not a list")
    for index, word in enumerate(guesses):
        if not _is_word(word):
            raise InvalidLists(f"guesses[{index}]: {word!r} is not five letters from a to z")
    accepted = frozenset(guesses)
    tiers = tuple(_tier(index, tier) for index, tier in enumerate(answers))
    seen: set[str] = set()
    for tier in tiers:
        for word in tier:
            if word in seen:
                raise InvalidLists(f"answers: {word!r} twice")
            if word not in accepted:
                raise InvalidLists(f"answers: {word!r} is not among the guesses")
            seen.add(word)
    if len(seen) < MIN_ANSWERS:
        raise InvalidLists(f"answers: {len(seen)} words, {MIN_ANSWERS} at least")
    if len(accepted) < MIN_GUESSES:
        raise InvalidLists(f"guesses: {len(accepted)} words, {MIN_GUESSES} at least")
    return WordLists(tiers, accepted)


def _tier(index: int, tier: object) -> tuple[str, ...]:
    """The words of a tier, checked."""
    where = f"answers[{index}]"
    if not isinstance(tier, dict) or not _TIER_KEYS <= tier.keys():
        raise InvalidLists(f"{where}: not a tier {{id, min, max, count, words}}")
    words = tier["words"]
    if not isinstance(tier["id"], str):
        raise InvalidLists(f"{where}: its id is not a string")
    if not _number(tier["min"]) or not (tier["max"] is None or _number(tier["max"])):
        raise InvalidLists(f"{where}: its min or max is not a number")
    if not isinstance(words, list) or not words:
        raise InvalidLists(f"{where}: no words")
    count = tier["count"]
    if not isinstance(count, int) or isinstance(count, bool) or count != len(words):
        raise InvalidLists(f"{where}: count {count!r} for {len(words)} words")
    for position, entry in enumerate(words):
        at = f"{where}.words[{position}]"
        if not isinstance(entry, dict) or not _WORD_KEYS <= entry.keys():
            raise InvalidLists(f"{at}: not a word {{word, spelling, freq, kind}}")
        if not _is_word(entry["word"]):
            raise InvalidLists(f"{at}: {entry['word']!r} is not five letters from a to z")
        kind = entry["kind"]
        if (
            not isinstance(entry["spelling"], str)
            or not _number(entry["freq"])
            or not isinstance(kind, list)
            or not all(isinstance(each, str) for each in kind)
        ):
            raise InvalidLists(f"{at}: its spelling, freq or kind is not of the format")
    return tuple(entry["word"] for entry in words)


def _is_word(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and _WORD.fullmatch(value) is not None


def _number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)
