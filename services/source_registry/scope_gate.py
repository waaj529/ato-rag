"""Authoritative corpus scope boundary gate prior to retrieval."""

from dataclasses import dataclass
from enum import Enum
import re
from typing import Sequence

from packages.telemetry import span

# Near-domain Australian statutory & regulatory regimes outside the tax corpus
_OUT_OF_CORPUS_DOMAINS: tuple[tuple[str, re.Pattern, str], ...] = (
    ("foreign_jurisdiction", re.compile(r"\b(uk|hmrc|hm\s+revenue|manchester|new\s+zealand|auckland|irs|internal\s+revenue|vat\s+refund|401k|401\(k\)|tfsa|singapore|canada|ireland|w-8ben|1031\s+exchange)\b", re.I), "Foreign law"),
    ("fair_work_employment", re.compile(r"\b(fair\s+work|fwc\b|modern\s+award|minimum\s+wage|annual\s+leave\s+entitlement|unfair\s+dismissal|enterprise\s+agreement|national\s+employment\s+standards|nes\b|long\s+service\s+leave)\b", re.I), "Fair Work and industrial relations"),
    ("asic_corporate", re.compile(r"\b(asic\s+(form|fee|annual|registration)|form\s+201\b|company\s+incorporation\s+fee|director\s+id\b|afsl\b|australian\s+financial\s+services\s+licen[sc]e)\b", re.I), "ASIC corporate administration and licensing"),
    ("apra_prudential", re.compile(r"\b(apra\b|prudential\s+standard|cps\s+\d+|aps\s+\d+|capital\s+adequacy\s+ratio|bank\s+liquidity\s+coverage)\b", re.I), "APRA banking and insurance supervision"),
    ("accc_competition", re.compile(r"\b(accc\b|australian\s+consumer\s+law|acl\b|misleading\s+or\s+deceptive|merger\s+clearance|cartel\s+conduct)\b", re.I), "ACCC competition and consumer protection"),
    ("privacy_cyber", re.compile(r"\b(privacy\s+act\s+1988|oaic\b|australian\s+privacy\s+principles|app\s+guidelines|notifiable\s+data\s+breaches|essential\s+eight)\b", re.I), "Privacy Act and cybersecurity frameworks"),
    ("immigration_family", re.compile(r"\b(visa\s+subclass|tss\s+482|family\s+court|family\s+law\s+act|property\s+settlement\s+divorce)\b", re.I), "Immigration and family law"),
)

# Core in-scope Australian taxation, superannuation guarantee, ATO rulings, and tax cases
_IN_SCOPE_TAX_PATTERNS = re.compile(
    r"\b(itaa|taxation\s+administration\s+act|taa\s+1953|fbt|fbtaa|cgt|capital\s+gains\s+tax|"
    r"goods\s+and\s+services\s+tax|gst\b|franking|superannuation\s+guarantee|sgaa|"
    r"division\s+\d+|section\s+\d+-\d+|s\s+\d+-\d+|tr\s+\d+|td\s+\d+|lcr\s+\d+|pcg\s+\d+|"
    r"gstr\s+\d+|gstd\s+\d+|psla\s+\d+|ato\s+id|assessable\s+income|deductib|depreciat|"
    r"cost\s+base|small\s+business\s+cgt|franked\s+dividend|commissioner\s+of\s+taxation|"
    r"fct\s+v|re\s+dixon|part\s+iva|fringe\s+benefits)\b",
    re.I,
)


class ScopeStatus(str, Enum):
    IN_SCOPE = "IN_SCOPE"
    OUT_OF_CORPUS = "OUT_OF_CORPUS"
    AMBIGUOUS_SCOPE = "AMBIGUOUS_SCOPE"


@dataclass(frozen=True)
class ScopeDecision:
    status: ScopeStatus
    code: str
    reason: str
    domain: str


class CorpusScopeGate:
    """Verifies whether a query falls within the published Australian tax corpus."""

    def evaluate(self, query: str) -> ScopeDecision:
        with span("corpus_scope_evaluation"):
            clean_q = query.strip()

            # 1. Check explicit near-domain or foreign regimes not covered
            for domain_id, pat, description in _OUT_OF_CORPUS_DOMAINS:
                if pat.search(clean_q):
                    code = "FOREIGN_LAW" if domain_id == "foreign_jurisdiction" else "NEAR_DOMAIN_UNINDEXED"
                    reason = f"Subject matter ({description}) is not covered by the published FinTaxGPT Australian taxation and revenue law corpus."
                    return ScopeDecision(ScopeStatus.OUT_OF_CORPUS, code, reason, domain_id)

            # 2. Check clear Australian taxation / revenue statutory indicators
            if _IN_SCOPE_TAX_PATTERNS.search(clean_q):
                return ScopeDecision(ScopeStatus.IN_SCOPE, "IN_SCOPE_TAX_CORPUS", "Query targets Australian taxation legislation, rulings, or case law.", "australian_taxation")

            # 3. If neither explicit tax authority nor explicit out-of-corpus domain matched
            # mark as AMBIGUOUS_SCOPE so retrieval continues only under strict registered evidence verification
            return ScopeDecision(ScopeStatus.AMBIGUOUS_SCOPE, "AMBIGUOUS_LEGAL_SCOPE", "Query lacks explicit tax citations; requires registered tax evidence verification.", "ambiguous_australian_law")
