"""Words of Wordle: five letters, no accent, lower case.

`ANSWERS` are the words of the day; `EXTRA` are further words accepted as a try (conjugated
forms, plurals, rarer words) that never come up as an answer. Order of `ANSWERS` is kept: the
word of a day is picked by an index into it, so only append to it.
"""

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
