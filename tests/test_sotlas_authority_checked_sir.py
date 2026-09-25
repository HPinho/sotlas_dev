"""Strict checked-SIR composition for Phase-3 Authority Domains."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_authority_checked_sir_package"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name,
        PACKAGE_DIR / "__init__.py",
        submodule_search_locations=[str(PACKAGE_DIR)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


package = _load_package()
canonical_sir = importlib.import_module(f"{package.__name__}.canonical_sir")


MATCHING = """module app::authority_checked_sir;
@system(pci.config)
fn configure_pci() -> void { return; }
@system(pci.config)
fn boot() -> void {
    configure_pci();
    return;
}
"""


REPEATED = """module app::authority_checked_sir_repeated;
@system(pci.config)
fn configure_pci() -> void { return; }
@system(pci.config)
fn boot() -> void {
    configure_pci();
    configure_pci();
    return;
}
"""


LEGACY = """module app::authority_checked_sir_legacy;
@system
fn raw_hardware() -> void { return; }
@system
fn boot() -> void {
    raw_hardware();
    return;
}
"""


class SotlasAuthorityCheckedSITTests(unittest.TestCase):
    def test_strict_builder_lowers_named_authority_call_and_certifies_it(self):
        checked = package.analyze_source_phase1(
            MATCHING,
            filename="<authority-checked-sir>",
        )
        result = canonical_sir.build_canonical_checked_authority_sir(checked)
        sir = canonical_sir.load_canonical_sir()
        boot = next(item for item in result.module.functions if item.name == "boot")
        calls = [
            item
            for block in boot.blocks
            for item in block.instructions
            if isinstance(item, sir.CallInst)
        ]

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].callee, "configure_pci")
        self.assertFalse(calls[0].is_system)
        self.assertEqual(
            result.authority_certificate.function("boot").capabilities,
            ("pci.config",),
        )
        self.assertEqual(
            resu[˜]]Üš]WØÙ\YšXØ]K˜Ø[×Ùœ›ÛJ˜›ÛİŠVÌKœÚ\—ØØ[ØÛİ[ˆKˆ
BˆÙ[‹˜\ÜÙ\YJ™\İ[˜]]Üš]WÜØY™]KœİXØÙ\ÜÊB‚ˆYˆ\İÜ™\X]YØ]]Üš]WØØ[×Üİ\š]™WÚ[×ÜÚ\—ØWØÛİ[
Ù[ŠN‚ˆÚXÚÙYHXÚØYÙK˜[˜[^™WÜÛİ\˜ÙWÜ\ÙLJˆ‘TPUQˆš[[˜[YOH]]Üš]KXÚXÚÙY\Ú\‹\™\X]Yˆ‹ˆ
Bˆ™\İ[HØ[›ÛšXØ[ÜÚ\‹˜Z[ØØ[›ÛšXØ[ØÚXÚÙYØ]]Üš]WÜÚ\ŠÚXÚÙY
BˆÜ›İ\H™\İ[˜]]Üš]WØÙ\YšXØ]K˜Ø[×Ùœ›ÛJ˜›ÛİŠVÌBˆÙ[‹˜\ÜÙ\\]X[
Ü›İ\œÚ\—ØØ[ØÛİ[ŠBˆÙ[‹˜\ÜÙ\\]X[
[ŠÜ›İ\œÛİ\˜ÙWÜÚ[ÚYÊKŠBˆÙ[‹˜\ÜÙ\YJ™\İ[˜]]Üš]WÜØY™]KœİXØÙ\ÜÊB‚ˆYˆ\İÛYØXŞWØ]]Üš]WØØ[Ü™\Ù\™\×ÛÛÜŞ\İ[WÛX\šÙ\ŠÙ[ŠN‚ˆÚXÚÙYHXÚØYÙK˜[˜[^™WÜÛİ\˜ÙWÜ\ÙLJˆQĞPÖKˆš[[˜[YOH]]Üš]KXÚXÚÙY\Ú\‹[YØXŞOˆ‹ˆ
Bˆ™\İ[HØ[›ÛšXØ[ÜÚ\‹˜Z[ØØ[›ÛšXØ[ØÚXÚÙYØ]]Üš]WÜÚ\ŠÚXÚÙY
BˆÚ\ˆHØ[›ÛšXØ[ÜÚ\‹›ØYØØ[›ÛšXØ[ÜÚ\Š
Bˆ›ÛİH™^
][H›Üˆ][H[ˆ™\İ[›[Ù[K™[˜İ[ÛœÈYˆ][K›˜[YHOH˜›ÛİŠBˆØ[H™^
ˆ][Bˆ›Üˆ›ØÚÈ[ˆ›Ûİ˜›ØÚÜÂˆ›Üˆ][H[ˆ›ØÚËš[œİXİ[ÛœÂˆYˆ\Ú[œİ[˜ÙJ][KÚ\‹Ø[[œİ
Bˆ
B‚ˆÙ[‹˜\ÜÙ\YJ›Ûİš\×ÜŞ\İ[JBˆÙ[‹˜\ÜÙ\YJØ[š\×ÜŞ\İ[JBˆÙ[‹˜\ÜÙ\YJˆ™\İ[˜]]Üš]WØÙ\YšXØ]K™[˜İ[ÛŠ˜›ÛİŠK›YØXŞWİ[œ™\İšXİYˆ
BˆÙ[‹˜\ÜÙ\YJ™\İ[˜]]Üš]WÜØY™]KœİXØÙ\ÜÊB‚ˆYˆ\İÛİÛ™\œÚ\ÛÛ›WØZ[\—ÚÙY\×Ú]×ØÛÛ\]Xš[]WÜÚ\JÙ[ŠN‚ˆÚXÚÙYHXÚØYÙK˜[˜[^™WÜÛİ\˜ÙWÜ\ÙLJˆPUÒS‘Ëˆš[[˜[YOH]]Üš]K[İÛ™\œÚ\XÛÛ\]ˆ‹ˆ
BˆİÛ™\œÚ\[ˆHØ[›ÛšXØ[ÜÚ\‹˜Z[ØØ[›ÛšXØ[ØÚXÚÙYÛİÛ™\œÚ\ÜÚ\ŠˆÚXÚÙYˆ
BˆÙ[‹˜\ÜÙ\\Ó›İ›Û™JİÛ™\œÚ\›[Ù[JBˆÙ[‹˜\ÜÙ\\Ó›İ›Û™J[ŠB‚‚šYˆ×Û˜[YW×ÈOH—×ÛXZ[—×È‚ˆ[š]\İ›XZ[Š
B