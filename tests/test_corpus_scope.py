"""Tests for CorpusScopeGate and authoritative source-family scope boundaries."""

from services.source_registry import CorpusScopeGate, ScopeStatus


def test_in_scope_tax_legislation():
    gate = CorpusScopeGate()
    assert gate.evaluate("What is a CGT asset under Section 108-5 of the ITAA 1997?").status == ScopeStatus.IN_SCOPE
    assert gate.evaluate("What is the general deduction formula in Section 8-1?").status == ScopeStatus.IN_SCOPE
    assert gate.evaluate("What are taxable supplies under the GST Act?").status == ScopeStatus.IN_SCOPE


def test_in_scope_ato_guidance_and_rulings():
    gate = CorpusScopeGate()
    assert gate.evaluate("Under PCG 2016/5, what are the safe harbour arm's length terms for SMSFs?").status == ScopeStatus.IN_SCOPE
    assert gate.evaluate("What does Taxation Ruling TR 2006/2 say about service entity fees?").status == ScopeStatus.IN_SCOPE
    assert gate.evaluate("What is the holding in TD 2004/1 regarding share-market subscriptions?").status == ScopeStatus.IN_SCOPE


def test_in_scope_case_law():
    gate = CorpusScopeGate()
    assert gate.evaluate("What did the High Court rule in FCT v Myer Emporium Ltd (1987)?").status == ScopeStatus.IN_SCOPE
    assert gate.evaluate("What did the AAT hold in Re Dixon and FCT regarding scholarship stipends?").status == ScopeStatus.IN_SCOPE


def test_out_of_corpus_near_domain_australian_regimes():
    gate = CorpusScopeGate()
    dec_fwc = gate.evaluate("What is the Fair Work minimum wage rate for adult retail modern award workers?")
    assert dec_fwc.status == ScopeStatus.OUT_OF_CORPUS
    assert dec_fwc.code == "NEAR_DOMAIN_UNINDEXED"
    assert "Fair Work" in dec_fwc.reason

    dec_asic = gate.evaluate("What ASIC Form 201 registration fee is charged to incorporate a company?")
    assert dec_asic.status == ScopeStatus.OUT_OF_CORPUS
    assert dec_asic.code == "NEAR_DOMAIN_UNINDEXED"
    assert "ASIC" in dec_asic.reason

    dec_apra = gate.evaluate("What operational risk resilience requirements are mandated under APRA CPS 230?")
    assert dec_apra.status == ScopeStatus.OUT_OF_CORPUS
    assert dec_apra.code == "NEAR_DOMAIN_UNINDEXED"
    assert "APRA" in dec_apra.reason

    dec_accc = gate.evaluate("What penalties apply to cartel conduct under the Australian Consumer Law administered by ACCC?")
    assert dec_accc.status == ScopeStatus.OUT_OF_CORPUS
    assert dec_accc.code == "NEAR_DOMAIN_UNINDEXED"

    dec_privacy = gate.evaluate("What notifiable data breach notifications must be made to OAIC under Privacy Act 1988?")
    assert dec_privacy.status == ScopeStatus.OUT_OF_CORPUS
    assert dec_privacy.code == "NEAR_DOMAIN_UNINDEXED"


def test_out_of_corpus_foreign_law():
    gate = CorpusScopeGate()
    assert gate.evaluate("What is the penalty for early withdrawal from a US 401(k) under IRS rules?").status == ScopeStatus.OUT_OF_CORPUS
    assert gate.evaluate("How does the UK HMRC remittance basis work for non-domiciled individuals?").status == ScopeStatus.OUT_OF_CORPUS
    assert gate.evaluate("What is the TFSA contribution limit under Canadian tax law?").status == ScopeStatus.OUT_OF_CORPUS
    assert gate.evaluate("What corporate tax exemption applies to Singapore foreign dividend income?").status == ScopeStatus.OUT_OF_CORPUS


def test_ambiguous_legal_scope():
    gate = CorpusScopeGate()
    dec = gate.evaluate("What are the general rules regarding contract execution by agents?")
    assert dec.status == ScopeStatus.AMBIGUOUS_SCOPE
    assert dec.code == "AMBIGUOUS_LEGAL_SCOPE"
