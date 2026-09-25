"""Sotlas Compile — frontend canônico, segurança e lowering de produção."""

# Há uma única rota de compilação de produção: bootstrap + extensões oficiais +
# política de segurança/FFI. Ferramentas podem expor ASTs auxiliares, mas não
# podem possuir um segundo lowering ou uma segunda semântica executável.
from . import bootstrap as bootstrap
from .frontend_extensions import install as _install_frontend_extensions
from .language_safety import install as _install_language_safety
from .authority_frontend_safety import install as _install_authority_frontend_safety
from .region_indirect_safety import install as _install_region_indirect_safety
from .region_method_safety import install as _install_region_method_safety

_install_frontend_extensions(bootstrap)
_install_language_safety(bootstrap)
_install_region_indirect_safety(bootstrap)
_install_region_method_safety(bootstrap)
_install_authority_frontend_safety(bootstrap)

from .errors import SotlasError
from .phase1_pipeline import (
    Phase1CheckedModule,
    analyze_module_phase1,
    analyze_source_phase1,
)
from .canonical_sir import (
    CheckedAuthoritySIR,
    build_canonical_checked_authority_sir,
)

SotlasBootstrapError = bootstrap.SotlasBootstrapError
compile_source = bootstrap.compile_source
compile_project = bootstrap.compile_project
emit_c_project = bootstrap.emit_c_project

__all__ = [
    "bootstrap", "SotlasError", "SotlasBootstrapError", "compile_source",
    "compile_project", "emit_c_project", "Phase1CheckedModule",
    "analyze_module_phase1", "analyze_source_phase1", "CheckedAuthoritySIR",
    "build_canonical_checked_authority_sir",
]
