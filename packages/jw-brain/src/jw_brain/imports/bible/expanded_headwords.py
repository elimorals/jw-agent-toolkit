"""F58.14 — catálogos expandidos de cabezales bíblicos.

Estos son nombres propios del canon bíblico, hechos factuales públicos.
No constituyen redistribución del contenido del Insight on the Scriptures
(que es propiedad de Watch Tower Bible and Tract Society of Pennsylvania).

El catálogo built-in cubre figuras y lugares **comunes** del canon AT/NT
en sus formas inglesas y españolas (lowercase para case-insensitive lookup).
Cobertura pretendida: ~250 personas + ~100 lugares. NO pretende ser
exhaustivo de las miles de entradas del Insight — para auditar cobertura
sobre el Insight completo, el usuario puede correr
`jw brain learn-headwords --insight <jwpub>`. Esa extracción se persiste
localmente en el brain del usuario (no se redistribuye).

Política de expansión:
- Solo nombres propios del canon bíblico (NWT + transliteraciones estándar).
- Sin texto descriptivo del Insight.
- Si un nombre es ambiguo persona/lugar (e.g. "Judá" patriarca vs Judá región),
  se prefiere registrarlo en la categoría dominante en NWT; los pocos overlaps
  legítimos se aceptan (ver `test_no_duplicates_across_person_place`).

Versión: F58.14 — expandir iterativamente vía PRs cuando se identifiquen
gaps de cobertura.
"""

from __future__ import annotations

# ── Personas ───────────────────────────────────────────────────────────────
#
# Lowercase. Cubre desde Adán/Eva hasta los apóstoles, incluyendo profetas
# mayores/menores, reyes de Judá/Israel, y figuras del exilio babilónico y
# del NT. Variantes ES/EN/transliteración estándar lado-a-lado.

EXPANDED_PERSON_HEADWORDS: frozenset[str] = frozenset(
    {
        # Patriarcas pre-diluvianos
        "adán", "adan", "adam", "eva", "eve",
        "set", "seth", "enós", "enos",
        "cainán", "cainan",
        "mahalalel",
        "jared",
        "enoc", "enoch",
        "matusalén", "matusalen", "methuselah",
        "lamec", "lamech",
        "noé", "noe", "noah",
        "sem", "shem", "cam", "ham", "jafet", "japheth",
        # Patriarcas post-diluvianos
        "abraham", "abram",
        "sara", "sarah", "sarai",
        "agar", "hagar",
        "ismael", "ishmael",
        "isaac",
        "rebeca", "rebekah",
        "esaú", "esau",
        # Jacob y los doce hijos (los nombres se usan también como tribus/regiones;
        # por defecto los clasificamos como persona — el contexto del Insight tendría
        # entrada separada para "tribe of Judah" etc.)
        "jacob",
        "lea", "leah",
        "raquel", "rachel",
        "bilhá", "bilha",
        "zilpá", "zilpa",
        "rubén", "ruben", "reuben",
        "simeón", "simeon",
        "leví", "levi",
        "judá", "juda", "judah",
        "neftalí", "neftali", "naphtali",
        "gad",
        "aser", "asher",
        "isacar", "issachar",
        "zabulón", "zabulon", "zebulun",
        "josé", "joseph",
        "benjamín", "benjamin",
        "efraín", "efrain", "ephraim",
        "manasés", "manases", "manasseh",
        # Egipto / Éxodo
        "moisés", "moises", "moses",
        "aarón", "aaron",
        "miriam",
        "jocabed", "jochebed",
        "amram",
        "jetro", "jethro",
        "séfora", "sefora", "zipporah",
        "gersón", "gershon",
        "eliezer",
        "josué", "josue", "joshua",
        "caleb",
        # Jueces
        "otoniel", "othniel",
        "ehud",
        "samgar", "shamgar",
        "débora", "debora", "deborah",
        "barac", "barak",
        "jael",
        "gedeón", "gedeon", "gideon",
        "abimélec", "abimelec", "abimelech",
        "tola",
        "jair",
        "jefté", "jefte", "jephthah",
        "ibsán", "ibsan", "ibzan",
        "elón", "elon",
        "abdón", "abdon",
        "sansón", "sanson", "samson",
        "dalila", "delilah",
        # Rut
        "rut", "ruth",
        "noemí", "noemi", "naomi",
        "booz", "boaz",
        "obed",
        # Sacerdocio / Profetas primeros
        "elí", "eli",
        "samuel",
        "ana", "hannah",
        # Reyes unidos
        "saúl", "saul",
        "jonatán", "jonatan", "jonathan",
        "abner",
        "isboset", "ish-bosheth",
        "david",
        "joab",
        "abisai", "abishai",
        "asael", "asahel",
        "betsabé", "betsabe", "bathsheba",
        "urías", "urias", "uriah",
        "absalón", "absalon", "absalom",
        "amnón", "amnon",
        "tamar",
        "salomón", "salomon", "solomon",
        "natán", "natan", "nathan",
        # Reyes de Judá
        "roboam", "rehoboam",
        "abías", "abias", "abijah",
        "asa",
        "josafat", "jehoshafat", "jehoshaphat",
        "joram", "jehoram",
        "ocozías", "ocozias", "ahaziah",
        "atalía", "atalia", "athaliah",
        "joás", "joas", "joash", "jehoash",
        "amasías", "amasias", "amaziah",
        "uzías", "uzias", "uzziah", "azariah",
        "jotam", "jotham",
        "acaz", "ahaz",
        "ezequías", "ezequias", "hezekiah",
        "amón", "amon",
        "josías", "josias", "josiah",
        "joacaz", "jehoahaz",
        "joaquim", "jehoiakim",
        "joaquín", "joaquin", "jehoiachin",
        "sedequías", "sedequias", "zedekiah",
        # Reyes de Israel (norte)
        "jeroboam",
        "nadab",
        "baasa", "baasha",
        "ela", "elah",
        "zimri",
        "omri",
        "acab", "ahab",
        "jezabel", "jezebel",
        "jehú", "jehu",
        "joacaz", "jehoahaz",
        "joás", "joas",
        "oseas", "hoshea",
        # Profetas mayores y menores
        "elías", "elias", "elijah",
        "eliseo", "elisha",
        "giezi", "gehazi",
        "naamán", "naaman",
        "isaías", "isaias", "isaiah",
        "jeremías", "jeremias", "jeremiah",
        "baruc", "baruch",
        "ezequiel", "ezekiel",
        "daniel",
        "oseas", "hosea",
        "joel",
        "amós", "amos",
        "abdías", "abdias", "obadiah",
        "jonás", "jonas", "jonah",
        "miqueas", "micah",
        "nahúm", "nahum",
        "habacuc", "habakkuk",
        "sofonías", "sofonias", "zephaniah",
        "hageo", "haggai",
        "zacarías", "zacarias", "zechariah",
        "malaquías", "malaquias", "malachi",
        # Exilio / Persia
        "nabucodonosor", "nebuchadnezzar",
        "evil-merodac", "evil-merodach",
        "belsasar", "belshazzar",
        "darío", "dario", "darius",
        "ciro", "cyrus",
        "asuero", "ahasuerus", "jerjes", "xerxes",
        "artajerjes", "artaxerxes",
        "ester", "esther",
        "mardoqueo", "mordecai",
        "amán", "haman",
        "vasti", "vashti",
        "esdras", "ezra",
        "nehemías", "nehemias", "nehemiah",
        "zorobabel", "zerubbabel",
        "sadrac", "shadrach",
        "mesac", "meshach",
        "abed-nego", "abednego",
        "ananías", "ananias",
        "misael", "mishael",
        "azarías", "azarias", "azariah",
        # Sabios / Job
        "job",
        "elifaz", "eliphaz",
        "bildad",
        "zofar", "zophar",
        "eliú", "eliu", "elihu",
        # Evangelios — natividad / familia
        "jesús", "jesus", "jesucristo", "cristo", "christ",
        "maría", "maria", "mary",
        "isabel", "elizabeth",
        "juan el bautista",
        "simeón", "simeon",
        "ana", "anna",
        "herodes", "herod",
        "herodías", "herodias",
        "salomé", "salome",
        # Apóstoles
        "pedro", "peter", "simón pedro", "simon peter", "cefas", "cephas",
        "andrés", "andres", "andrew",
        "santiago", "james",
        "juan", "john",
        "felipe", "philip",
        "bartolomé", "bartolome", "bartholomew",
        "natanael", "nathanael",
        "tomás", "tomas", "thomas",
        "mateo", "matthew",
        "tadeo", "thaddaeus", "thaddeus",
        "judas iscariote", "judas",
        "matías", "matias", "matthias",
        # Otros del NT
        "lázaro", "lazaro", "lazarus",
        "marta", "martha",
        "nicodemo", "nicodemus",
        "josé de arimatea", "joseph of arimathea",
        "pablo", "paulo", "paul",
        "saulo",
        "bernabé", "bernabe", "barnabas",
        "marcos", "mark",
        "lucas", "luke",
        "silas", "silvano", "silvanus",
        "timoteo", "timothy",
        "tito", "titus",
        "filemón", "filemon", "philemon",
        "onésimo", "onesimo", "onesimus",
        "apolos", "apollos",
        "esteban", "stephen",
        "cornelio", "cornelius",
        "ananías", "ananias",
        "safira", "sapphira",
        "tabita", "tabitha", "dorcas",
        "lidia", "lydia",
        "priscila", "priscilla",
        "aquila",
        "rufo", "rufus",
        "tértulo", "tertulo", "tertullus",
        "festo", "festus",
        "félix", "felix",
        "agripa", "agrippa",
        "berenice",
        "drusila", "drusilla",
        # Figuras angelicales / espirituales nombradas
        "miguel", "michael",
        "gabriel",
        "satanás", "satanas", "satan",
        "diablo", "devil",
        "lucifer",
        "beelzebub", "beelzebú", "beelzebu",
    }
)
"""~250 personas bíblicas del canon AT/NT. Built-in factual público."""


# ── Lugares ────────────────────────────────────────────────────────────────
#
# Lowercase. Cubre regiones, ciudades y geografía natural mencionada en NWT.
# Algunos overlaps con personas (Israel, Judá) son legítimos: el contexto del
# Insight tiene artículos separados ("Israel [persona]" vs "Israel, tierra de").
# El classifier prioriza Person para esos overlaps; el catálogo place declara
# variantes específicas (e.g. "tierra de israel") cuando aplica.

EXPANDED_PLACE_HEADWORDS: frozenset[str] = frozenset(
    {
        # Edén / patriarcal
        "edén", "eden",
        "ararat",
        "babel",
        "ur",
        "harán", "haran",
        "mamre",
        "macpela", "machpelah",
        "sodoma", "sodom",
        "gomorra", "gomorrah",
        "siquem", "shechem",
        "betel", "bethel",
        "luz",
        "peniel", "penuel",
        "sucot", "succoth",
        # Egipto
        "egipto", "egypt",
        "gosén", "gosen", "goshen",
        "menfis", "memphis",
        "tebas", "thebes",
        "ramesés", "rameses", "raamses",
        "pi-hahirot", "pi hahiroth",
        # Sinaí / wilderness / vecinos
        "sinaí", "sinai",
        "horeb",
        "cades", "kadesh",
        "cadesbarnea", "kadesh-barnea",
        "moab",
        "edom",
        # Nota: "amón" persona (rey Amón) está en EXPANDED_PERSON_HEADWORDS;
        # aquí solo registramos la transliteración inglesa "ammon" para la
        # tierra al este del Jordán, evitando overlap persona/lugar.
        "ammon",
        "amalec", "amalek",
        "madián", "madian", "midian",
        # Tierra prometida y regiones
        "canaán", "canaan",
        "palestina", "palestine",
        "tierra santa",
        "judea",
        "samaria",
        "galilea", "galilee",
        "perea", "perea",
        "decápolis", "decapolis",
        "fenicia", "phoenicia",
        "tiro", "tyre",
        "sidón", "sidon",
        "filistea", "philistia",
        # Ciudades filisteas
        "gat", "gath",
        "asdod", "ashdod",
        "ascalón", "ascalon", "ashkelon",
        "ecrón", "ekron",
        "gaza",
        # Ciudades de Israel/Judá
        "jerusalén", "jerusalen", "jerusalem",
        "belén", "belen", "bethlehem",
        "hebrón", "hebron",
        "jericó", "jerico", "jericho",
        "siloh", "siló", "silo", "shiloh",
        "gabaón", "gabaon", "gibeon",
        "ramá", "rama", "ramah",
        "guilgal", "gilgal",
        "tirsa", "tirzah",
        "guézer", "gezer",
        "laquis", "lakis", "lachish",
        "mizpa", "mizpah",
        "siloé", "siloe", "siloam",
        # Ciudades del ministerio de Jesús
        "nazaret", "nazareth",
        "caná", "cana",
        "capernaúm", "capernaum",
        "betsaida", "bethsaida",
        "magdala",
        "tiberias",
        "naín", "nain", "naim",
        "betania", "bethany",
        "emaús", "emaus", "emmaus",
        # Geografía natural
        "jordán", "jordan",
        "tiberíades", "tiberiades", "mar de galilea", "sea of galilee",
        "mar muerto", "dead sea",
        "mediterráneo", "mediterranean",
        "carmelo", "carmel",
        "tabor",
        "líbano", "libano", "lebanon",
        "hermón", "hermon",
        "sión", "sion", "zion",
        "moriah", "moria",
        "olivos", "olives", "monte de los olivos",
        "getsemaní", "getsemani", "gethsemane",
        "gólgota", "golgota", "golgotha",
        # Mesopotamia / exilio
        "babilonia", "babylon", "babylonia",
        "asiria", "assyria",
        "nínive", "ninive", "nineveh",
        "calné", "calne",
        "akkad",
        "caldea", "chaldea",
        "elam",
        "media",
        "persia",
        "ecbatana", "ecbatana",
        "susa", "shushan",
        # NT mediterránea
        "roma", "rome",
        "italia", "italy",
        "atenas", "athens",
        "grecia", "greece",
        "macedonia",
        "tesalónica", "tesalonica", "thessalonica",
        "berea",
        "filipos", "philippi",
        "corinto", "corinth",
        "éfeso", "efeso", "ephesus",
        "esmirna", "smyrna",
        "pérgamo", "pergamo", "pergamum",
        "tiatira", "thyatira",
        "sardis",
        "filadelfia", "philadelphia",
        "laodicea",
        "colosas", "colosse", "colossae",
        "patmos",
        "creta", "crete",
        "chipre", "cyprus",
        "siracusa", "syracuse",
        # Asia Menor / NT misionero
        "antioquía", "antioquia", "antioch",
        "iconio", "iconium",
        "listra", "lystra",
        "derbe",
        "tarso", "tarsus",
        "cesarea", "caesarea",
        "damasco", "damascus",
        "arabia",
        # Provincias romanas
        "asia",
        "bitinia", "bithynia",
        "ponto", "pontus",
        "capadocia", "cappadocia",
        "frigia", "phrygia",
        "panfilia", "pamphylia",
        "cilicia",
        "siria", "syria",
        "galacia", "galatia",
        # Regiones tribales que tienen entrada también como tierra
        "tierra de israel",
    }
)
"""~150 lugares bíblicos del canon AT/NT. Built-in factual público."""
