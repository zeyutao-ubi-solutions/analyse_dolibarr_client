"""Company-name normalisation used to match order customers to the third-party registry.

All functions are pure and deterministic. They never guess: two names match only when
their normalised keys are identical. No prefix or edit-distance matching happens here.
"""

from __future__ import annotations

import re
import unicodedata

# Legal-form token sequences removed from the end of a name (repeatedly), after
# accents/punctuation are normalised. Dots are removed before tokenising, so "S.A.S."
# arrives as "SAS" and "S. A." as "S A"; both spellings are listed.
LEGAL_SUFFIXES: tuple[tuple[str, ...], ...] = tuple(
    tuple(s.split())
    for s in [
        # France
        "SA", "SAS", "SASU", "SARL", "EURL", "SNC", "SCOP", "SCA", "SCS", "SEM", "SELARL",
        "S A", "S A S", "S A R L",
        # Spain / Portugal / Latin America
        "SL", "SLU", "SLL", "SAU", "S L", "S L U", "S A U", "LDA", "LTDA",
        "SA DE CV", "S A DE C V", "SAPI DE CV", "S DE RL DE CV",
        # Germany / Austria / Switzerland
        "GMBH", "AG", "KG", "UG", "GMBH CO KG", "AG CO KG", "MBH",
        # UK / US / Commonwealth
        "LTD", "LIMITED", "PLC", "LLP", "LLC", "INC", "PVT LTD", "PRIVATE LIMITED",
        "PTY LTD", "PTY",
        # Benelux
        "BV", "NV", "BVBA", "SPRL", "SRL", "B V", "N V",
        # Italy
        "SPA", "S P A", "S R L",
        # Poland / Central Europe
        "SP Z O O", "SP ZOO", "SPZOO", "SP K", "SP J", "SRO", "S R O", "AS", "KFT", "ZRT",
        "DOO", "D O O",
        # Nordics
        "AB", "OY", "OYJ", "APS", "A S",
        # Asia
        "SDN BHD", "BHD",
    ]
)

# Leading legal forms (only unambiguous ones are stripped at the start of a name).
LEGAL_PREFIXES: tuple[tuple[str, ...], ...] = tuple(
    tuple(s.split()) for s in ["SAS", "SARL", "SASU", "EURL", "STE", "STE SAS"]
)

# Used only to detect intercompany customers ("Groupe Page Up" -> "PAGE UP"), never
# for the main customer -> third-party match.
GROUP_WORDS = frozenset({"GROUPE", "GROUP", "GRUPO", "GRUPPO", "GRUPA"})

_PAREN = re.compile(r"\([^)]*\)|\[[^\]]*\]")
_DOMAIN = re.compile(r"\.(com|fr|es|de|eu|net|org|co\.uk|uk|io)\b", re.IGNORECASE)
_NON_ALNUM = re.compile(r"[^0-9A-Z]+")
_SPACES = re.compile(r"\s+")


def _text(value: object) -> str | None:
    """Return the value as a str, or None for None/NaN/non-strings."""
    return value if isinstance(value, str) else None


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def exact_key(name: object) -> str | None:
    """Brief's rule 1: upper(trim(name))."""
    name = _text(name)
    if name is None:
        return None
    key = name.strip().upper()
    return key or None


def basic_key(name: object) -> str | None:
    """Accents removed, upper case, dots/apostrophes dropped, other punctuation -> space."""
    name = _text(name)
    if name is None:
        return None
    text = strip_accents(name).upper()
    text = text.replace(".", "").replace("'", "").replace("’", "")
    text = _NON_ALNUM.sub(" ", text)
    text = _SPACES.sub(" ", text).strip()
    return text or None


def _strip_sequences(
    tokens: list[str], sequences: tuple[tuple[str, ...], ...], *, from_end: bool
) -> list[str]:
    """Remove ONE legal-form sequence (the longest that fits) from one end.

    A single pass on purpose: repeated stripping turns "Creaciones B V s.l." into
    "CREACIONES", a key generic enough to collide with unrelated companies.
    """
    for seq in sorted(sequences, key=len, reverse=True):
        n = len(seq)
        if len(tokens) <= n:
            continue  # never strip the whole name
        part = tokens[-n:] if from_end else tokens[:n]
        if tuple(part) == seq:
            return tokens[:-n] if from_end else tokens[n:]
    return tokens


def core_key(name: object) -> str | None:
    """basic_key, minus parenthetical qualifiers, web domains and legal-form tokens.

    Falls back to basic_key when stripping would leave nothing (e.g. a customer
    literally named "SAS").
    """
    name = _text(name)
    if name is None:
        return None
    text = _PAREN.sub(" ", name)
    text = _DOMAIN.sub(" ", text)
    base = basic_key(text)
    if base is None:
        return basic_key(name)
    tokens = base.split()
    tokens = _strip_sequences(tokens, LEGAL_SUFFIXES, from_end=True)
    tokens = _strip_sequences(tokens, LEGAL_PREFIXES, from_end=False)
    return " ".join(tokens) or basic_key(name)


def group_free_key(name: object) -> str | None:
    """core_key without words like GROUPE/GROUP. Only for intercompany detection."""
    key = core_key(name)
    if key is None:
        return None
    tokens = [t for t in key.split() if t not in GROUP_WORDS]
    return " ".join(tokens) or key


def lookup_name(name: object) -> str | None:
    """Human-readable search name: original casing/accents kept, whitespace collapsed,
    parenthetical qualifiers, web domains and one trailing/leading legal form removed."""
    name = _text(name)
    if name is None:
        return None
    text = _SPACES.sub(" ", _DOMAIN.sub(" ", _PAREN.sub(" ", name))).strip(" ,;-")
    if not text:
        return name.strip() or None
    words = text.split(" ")
    words = _strip_words(words, LEGAL_SUFFIXES, from_end=True)
    words = _strip_words(words, LEGAL_PREFIXES, from_end=False)
    return " ".join(words).strip(" ,;-") or name.strip()


def _strip_words(
    words: list[str], sequences: tuple[tuple[str, ...], ...], *, from_end: bool
) -> list[str]:
    """Same as _strip_sequences but on raw words ("S.A.S." is one word, "S. A." two)."""
    for width in range(min(4, len(words) - 1), 0, -1):
        part = words[-width:] if from_end else words[:width]
        key = basic_key(" ".join(part))
        if key is None:
            continue
        for seq in sequences:
            if key == " ".join(seq) or key.replace(" ", "") == "".join(seq):
                kept = words[:-width] if from_end else words[width:]
                return " ".join(kept).strip(" ,;-").split(" ")
    return words


# --- Notes / flags derived from the name -------------------------------------------

_LOCATION_WORDS = re.compile(
    r"\b(MAGASIN|AGENCE|SITE|USINE|ENTREPOT|DEPOT|STORE|SHOP|BOUTIQUE|PLANT|BRANCH|"
    r"ETABLISSEMENT|SUCCURSALE|DELEGACION|SUCURSAL|FILIALE|CENTRE|CENTER|HOTEL|HOPITAL|"
    r"HOSPITAL|CLINIQUE|CAMPUS|LAVANDERIA|BLANCHISSERIE)\b"
)

# Words that suggest an RFID/AIDC integrator, reseller, consultant or peer rather than an
# end user. Kept narrow on purpose: generic words such as SYSTEMS, TECHNOLOGIES, DATA or a
# bare "ID" hit too many end customers (Safran Landing Systems, Id Verde, ID Logistics).
_INTEGRATOR_WORDS = re.compile(
    r"\b(RFID|TRAK|BARCODE|CODES? ?BARRES?|IDENTIFICATION|AIDC|TRACABILITE|TRAZABILIDAD|"
    r"INTEGRATION|INTEGRATEURS?|INTEGRATORS?|INTEGRADOR\w*|INFORMATIQUE|INFORMATICA|"
    r"COMPUTERS?|SOFTWARE|LOGICIELS?|ETIQUET\w*|LABELS?|LABELLING|AUTOMATISMES?|"
    r"CONSULT\w*)\b"
)

# AIDC / RFID manufacturers and resellers seen as peers of UBI (name tokens).
_KNOWN_PEERS = re.compile(
    r"\b(ZEBRA|HONEYWELL|DATALOGIC|COPPERNIC|IMPINJ|NEDAP|SATO|BRADY|INTERMEC|BLUEBIRD|"
    r"UNITECH|NEWLAND|CIPHERLAB|STID|FEIG|INVENGO|CONFIDEX|SMARTRAC|TAGEOS|DATAMARS|"
    r"AVERY DENNISON|CHECKPOINT|SCC|SOTI)\b"
)


def name_notes(name: object) -> list[str]:
    """Short notes about how the raw name looks (site/branch qualifiers, etc.)."""
    name = _text(name)
    if not name:
        return ["无客户名称"]
    notes: list[str] = []
    upper = basic_key(name) or ""
    if _PAREN.search(name):
        notes.append("名称含括号限定")
    if re.search(r"\s[-–/]\s", name):
        notes.append("名称含分支/地点后缀")
    if _LOCATION_WORDS.search(upper):
        notes.append("名称含地点/门店词")
    if re.search(r"\b\d{2,}\b", upper):
        notes.append("名称含编号")
    return notes


def integrator_keywords(name: object) -> list[str]:
    name = _text(name)
    if not name:
        return []
    upper = basic_key(name) or ""
    hits = {m.group(0) for m in _INTEGRATOR_WORDS.finditer(upper)}
    hits |= {f"peer:{m.group(0)}" for m in _KNOWN_PEERS.finditer(upper)}
    return sorted(hits)


# --- Country ------------------------------------------------------------------------

_COUNTRY_ISO = {
    "FRANCE": "FR", "FR": "FR", "FRANCE LA REUNION": "RE", "ROUEN": "FR",
    "SPAIN": "ES", "ESPANA": "ES", "ESPAGNE": "ES", "ESPALA": "ES", "ES": "ES",
    "UNITED KINGDOM": "GB", "UK": "GB", "GB": "GB",
    "SWITZERLAND": "CH", "UNITED STATES": "US", "PORTUGAL": "PT", "PROTUGAL": "PT",
    "GERMANY": "DE", "DE": "DE", "BELGIUM": "BE", "POLAND": "PL", "NERDERLAND": "NL",
    "NETHERLANDS": "NL", "CHINA": "CN", "MEXICO": "MX", "ITALY": "IT", "ITALIA": "IT",
    "SENEGAL": "SN", "LUXEMBOURG": "LU", "SWEDEN": "SE", "ROMANIA": "RO", "GABON": "GA",
    "PAKISTAN": "PK", "FINLAND": "FI", "AUSTRIA": "AT", "INDIA": "IN", "COLOMBIA": "CO",
    "COTE D IVOIRE": "CI", "NORWAY": "NO", "SOUTH COREA": "KR", "SOUTH KOREA": "KR",
    "MOROCCO": "MA", "GREECE": "GR", "DJIBUTI": "DJ", "DJIBOUTI": "DJ", "IRELAND": "IE",
    "SLOVAKIA": "SK", "DANEMARK": "DK", "DENMARK": "DK", "MACEDONIA": "MK",
    "AUSTRALIA": "AU", "MALAYSIA": "MY", "FRENCH POLYNESIA": "PF", "SINGAPORE": "SG",
    "HUNGARY": "HU", "URUGUAY": "UY", "TURKIYE": "TR", "TURKEY": "TR", "CYPRUS": "CY",
    "TUNISIA": "TN",
}


def country_iso(raw: object) -> str | None:
    """Map the free-text COUNTRY_CODE of the orders mart to ISO-3166 alpha-2."""
    key = basic_key(raw)
    if key is None:
        return None
    return _COUNTRY_ISO.get(key)


# Words too common to show that two names refer to the same company.
_GENERIC_WORDS = frozenset(
    {
        "GROUPE", "GROUP", "FRANCE", "SERVICES", "SERVICE", "LOGISTIQUE", "LOGISTICS", "TRANSPORT",
        "TRANSPORTS", "DE", "DES", "DU", "LA", "LE", "LES", "ET", "AND", "THE", "SOCIETE", "COMPANY",
        "CO", "INTERNATIONAL", "HOLDING", "SA", "SAS",
    }
)


def names_unrelated(a: object, b: object) -> bool:
    """True when two names share no significant word after core-key normalization.

    Used to flag customers whose order name and billed registry name look like different
    companies (end customer vs reseller, brand vs legal name, group vs subsidiary).
    Returns False when either name is missing: there is nothing to compare.
    """
    ka, kb = core_key(a), core_key(b)
    if not ka or not kb:
        return False
    return not ((set(ka.split()) - _GENERIC_WORDS) & (set(kb.split()) - _GENERIC_WORDS))


_DOMAIN_STOP_LABELS = frozenset({"www", "mail", "email", "fr", "es", "uk", "co", "com", "net", "org", "group", "groupe"})


def domain_matches_name(domain: object, *names: object) -> bool:
    """True when a web domain visibly belongs to one of the names.

    The domain's labels (minus TLDs and www/mail) are compared with the names' significant
    words: a word of 3+ letters inside a label (``cerp-rrm.com`` ~ CERP RHIN RHONE,
    ``skippergroupe.com`` ~ SKIPPER TECHNOLOGIES), or a label of 4+ letters inside the
    name written without spaces (``grandsmoulinsdeparis.com``). A parent brand that
    shares no word (``emilfrey.fr`` for PBO) gives False.
    """
    if not isinstance(domain, str) or not domain:
        return False
    host_labels = domain.lower().split(".")
    labels = [p for lbl in host_labels[:-1] for p in re.split(r"[-_\d]+", lbl) if p and p not in _DOMAIN_STOP_LABELS]
    if not labels:
        return False
    for name in names:
        key = core_key(name)
        if not key:
            continue
        words = [w.lower() for w in key.split() if w not in _GENERIC_WORDS and len(w) >= 3]
        joined = key.replace(" ", "").lower()
        if any(w in lbl for w in words for lbl in labels):
            return True
        if any(len(lbl) >= 4 and lbl.upper() not in _GENERIC_WORDS and lbl in joined for lbl in labels):
            return True
        # Initials: cfigroupe.com ~ Compagnie Francaise Informatique, fft.fr ~ Federation
        # Francaise de Tennis (with and without the small words).
        all_words = key.lower().split()
        content = [w for w in all_words if w.upper() not in _SMALL_WORDS]
        for acro in {"".join(w[0] for w in all_words), "".join(w[0] for w in content)}:
            if len(acro) >= 3 and any(lbl.startswith(acro) for lbl in labels):
                return True
    return False


_SMALL_WORDS = frozenset({"DE", "DES", "DU", "LA", "LE", "LES", "ET", "AND", "THE", "OF", "D", "L", "Y", "E"})
