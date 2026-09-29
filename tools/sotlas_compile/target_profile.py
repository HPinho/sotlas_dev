"""Canonical target-profile contract for the production Sotlas frontend.

Target profiles are contextual at the file header so adding the contract does not
reserve ordinary identifiers such as ``native`` or ``web`` elsewhere in source.
The parser records one immutable semantic fact on each module; later backend
layers consume that fact instead of re-reading source text.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TargetProfile:
    name: str
    freestanding: bool
    hosted: bool
    web: bool


TARGET_NATIVE = TargetProfile("native", freestanding=False, hosted=True, web=False)
TARGET_BARECORE = TargetProfile("barecore", freestanding=True, hosted=False, web=False)
TARGET_WEB = TargetProfile("web", freestanding=False, hosted=False, web=True)

_TARGETS = {
    profile.name: profile
    for profile in (TARGET_NATIVE, TARGET_BARECORE, TARGET_WEB)
}


def target_profile_of(module) -> TargetProfile:
    """Return the canonical target profile for a parsed module."""
    name = getattr(module, "target_profile", "native")
    try:
        return _TARGETS[name]
    except KeyError as error:
        raise ValueError(f"unknown Sotlas target profile: {name!r}") from error


def install(bootstrap) -> None:
    """Install target-header parsing into the one canonical frontend."""
    if getattr(bootstrap, "_TARGET_PROFILE_FRONTEND_INSTALLED", False):
        return

    base_parser = bootstrap.Parser

    class TargetProfileParser(base_parser):
        """Parse an optional target header before the mandatory module header."""

        def _accept_contextual_word(self, word: str):
            token = self.current
            if token.text == word:
                self.at += 1
                return token
            return None

        def _parse_target_profile(self):
            explicit = False
            profile = TARGET_NATIVE

            target_token = self._accept_contextual_word("target")
            if target_token is not None:
                explicit = True
                profile_token = self.current
                if profile_token.kind in (";", "EOF"):
                    raise bootstrap.SotlasBootstrapError(
                        "target profile name expected after 'target'",
                        profile_token.line,
                        profile_token.column,
                        self.filename,
                        self.source,
                    )
                self.at += 1
                profile = _TARGETS.get(profile_token.text)
                if profile is None:
                    raise bootstrap.SotlasBootstrapError(
                        f"unsupported target profile {profile_token.text!r}",
                        profile_token.line,
                        profile_token.column,
                        self.filename,
                        self.source,
                    )
                self.expect(";")
            else:
                barecore_token = self._accept_contextual_word("barecore")
                if barecore_token is not None:
                    explicit = True
                    profile = TARGET_BARECORE
                    self.expect(";")

            if self.current.text in ("target", "barecore"):
                duplicate = self.current
                raise bootstrap.SotlasBootstrapError(
                    "target profile may be declared only once before module",
                    duplicate.line,
                    duplicate.column,
                    self.filename,
                    self.source,
                )
            return profile, explicit

        def parse(self):
            profile, explicit = self._parse_target_profile()
            module = super().parse()
            module.target_profile = profile.name
            module.target_profile_facts = profile
            module.target_profile_explicit = explicit
            module.is_barecore = profile.freestanding
            return module

    bootstrap.Parser = TargetProfileParser
    bootstrap.TargetProfile = TargetProfile
    bootstrap.TARGET_NATIVE = TARGET_NATIVE
    bootstrap.TARGET_BARECORE = TARGET_BARECORE
    bootstrap.TARGET_WEB = TARGET_WEB
    bootstrap.target_profile_of = target_profile_of
    bootstrap._TARGET_PROFILE_FRONTEND_INSTALLED = True
