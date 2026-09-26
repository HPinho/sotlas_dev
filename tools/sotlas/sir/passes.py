"""Passes de Análise e Otimização do SIR.

Implementa verificações e otimizações essenciais em nível SIR:
1. Definite Initialization (DI): valida se variáveis são inicializadas antes de leitura.
2. Ownership & Safety Verification: valida privilégios de chamadas @system e ponteiros.
3. Dead Code Elimination (DCE): elimina blocos e instruções inalcançáveis após retorno.
4. Branch Folding Pass (Colapso de Ramos): funde saltos redundantes e desvios desnecessários.
5. Redundant Load Elimination: detecta cargas redundantes de slots de memória recém-armazenados.
"""
from __future__ import annotations
from typing import List, Set, Dict, Optional
from .instructions import (
    SIRModule, SIRFunction, SIRBasicBlock, SIRInstruction,
    SIREffectSummary,
    AllocStackInst, StoreInst, LoadInst, CallInst, ReturnInst,
    BranchInst, CondBranchInst, SIRValue, PhiInst, BoundsCheckInst,
    RetainInst, ReleaseInst, SystemOpInst, AsmInst, AwaitInst,
)


class SIRPassResult:
    def __init__(self, success: bool = True, errors: List[str] | None = None, changed: bool = False):
        self.success = success
        self.errors = errors or []
        self.changed = changed


_EFFECT_ORDER = (
    "alloc", "blocking", "async", "io", "sync", "unsafe", "volatile",
    "system", "unknown_call",
)
_KNOWN_EFFECTS = frozenset(_EFFECT_ORDER)
_CALL_EFFECTS = {
    "alloc": "alloc",
    "allocate": "alloc",
    "heap_allocate": "alloc",
    "malloc": "alloc",
    "sleep": "blocking",
    "block_on": "blocking",
    "wait_for_event": "blocking",
    "blocking_read": "blocking",
    "io_read": "io",
    "io_write": "io",
    "print": "io",
    "println": "io",
    "read": "io",
    "write": "io",
    "lock": "sync",
    "unlock": "sync",
    "mutex_lock": "sync",
    "mutex_unlock": "sync",
    "spin_lock": "sync",
    "spin_unlock": "sync",
}


class EffectInferencePass:
    """Infer conservative direct and transitive effects over the SIR call graph."""

    def run(self, module: SIRModule) -> SIRPassResult:
        errors: list[str] = []
        functions: dict[str, SIRFunction] = {}
        for function in module.functions:
            if function.name in functions:
                errors.append(
                    f"sir effect error: duplicate function {function.name!r}"
                )
            functions[function.name] = function
        if errors:
            return SIRPassResult(success=False, errors=errors)

        direct: dict[str, set[str]] = {name: set() for name in functions}
        callees: dict[str, set[str]] = {name: set() for name in functions}
        unresolved: dict[str, set[str]] = {name: set() for name in functions}
        for name, function in functions.items():
            source_summary = function.source_effect_summary
            if source_summary is not None:
                direct[name].update(source_summary.direct_effects)
                unresolved[name].update(source_summary.unresolved_calls)
            for block in function.blocks:
                for instruction in block.instructions:
                    if isinstance(instruction, CallInst):
                        effect = _CALL_EFFECTS.get(instruction.callee)
                        if effect is not None:
                            direct[name].add(effect)
                        elif instruction.callee in functions:
                            callees[name].add(instruction.callee)
                        else:
                            direct[name].add("unknown_call")
                            unresolved[name].add(instruction.callee)
                    elif isinstance(instruction, AwaitInst):
                        direct[name].add("async")
                    elif isinstance(instruction, AsmInst):
                        direct[name].add("unsafe")
                        if instruction.is_volatile:
                            direct[name].add("volatile")
                    elif isinstance(instruction, SystemOpInst):
                        direct[name].add("system")

        inferred = {name: set(effects) for name, effects in direct.items()}
        for name, function in functions.items():
            source_summary = function.source_effect_summary
            if source_summary is not None:
                inferred[name].update(source_summary.transitive_effects)
        unresolved_reachable = {
            name: set(calls) for name, calls in unresolved.items()
        }
        changed = True
        while changed:
            changed = False
            for name in functions:
                for callee in callees[name]:
                    prior_effect_count = len(inferred[name])
                    prior_call_count = len(unresolved_reachable[name])
                    inferred[name].update(inferred[callee])
                    unresolved_reachable[name].update(
                        unresolved_reachable[callee]
                    )
                    if (
                        len(inferred[name]) != prior_effect_count
                        or len(unresolved_reachable[name]) != prior_call_count
                    ):
                        changed = True

        summaries: dict[str, SIREffectSummary] = {}
        for name, function in functions.items():
            source_summary = function.source_effect_summary
            declared = function.declared_effects
            if declared is None and source_summary is not None:
                declared = source_summary.declared_effects
            if declared is not None:
                if not isinstance(declared, tuple) or any(
                    not isinstance(effect, str) for effect in declared
                ):
                    errors.append(
                        f"sir effect error: declared effects for {name!r} "
                        "must be a tuple of names"
                    )
                    declared_set: set[str] = set()
                else:
                    declared_set = set(declared)
                    invalid = declared_set - _KNOWN_EFFECTS
                    if invalid:
                        errors.append(
                            f"sir effect error: unknown declared effects for "
                            f"{name!r}: {', '.join(sorted(invalid))}"
                        )
                    missing = inferred[name] - declared_set
                    if missing:
                        errors.append(
                            f"sir effect error: declared effects for {name!r} "
                            f"omit inferred effects: {', '.join(sorted(missing))}"
                        )
                    if (
                        unresolved_reachable[name]
                        and "unknown_call" not in declared_set
                    ):
                        errors.append(
                            f"sir effect error: declared effects for {name!r} "
                            "omit inferred effects: unknown_call"
                        )

            summaries[name] = SIREffectSummary(
                direct_effects=tuple(
                    effect for effect in _EFFECT_ORDER if effect in direct[name]
                ),
                transitive_effects=tuple(
                    effect for effect in _EFFECT_ORDER if effect in inferred[name]
                ),
                unresolved_calls=tuple(sorted(unresolved_reachable[name])),
                declared_effects=declared,
            )

        changed_summary = summaries != module.effect_summaries
        module.effect_summaries = summaries
        for name, function in functions.items():
            effects = summaries[name].transitive_effects
            if function.inferred_effects != effects:
                changed_summary = True
            function.inferred_effects = effects
        return SIRPassResult(
            success=not errors,
            errors=errors,
            changed=changed_summary,
        )


class DefiniteInitializationPass:
    """Verifica se variáveis alocadas no stack recebem um store antes de qualquer load."""
    def run(self, module: SIRModule) -> SIRPassResult:
        errors = []
        for fn in module.functions:
            initialized_slots: Set[str] = set()
            for block in fn.blocks:
                for inst in block.instructions:
                    if isinstance(inst, StoreInst):
                        initialized_slots.add(inst.destination.name)
                    elif isinstance(inst, LoadInst):
                        if inst.source.name.startswith("slot_") and inst.source.name not in initialized_slots:
                            errors.append(
                                f"sir error: variável '{inst.source.name}' lida antes de ser inicializada na função '{fn.name}'"
                            )
        return SIRPassResult(success=len(errors) == 0, errors=errors)


class SystemCapabilitySafetyPass:
    """Verifica se operações marcadas com @system só são chamadas em contextos autorizados."""
    def run(self, module: SIRModule) -> SIRPassResult:
        errors = []
        for fn in module.functions:
            for block in fn.blocks:
                for inst in block.instructions:
                    if isinstance(inst, CallInst) and inst.is_system:
                        if not fn.is_system:
                            errors.append(
                                f"sir safety error: chamada para função @system '{inst.callee}' "
                                f"em função não-privilegiada '{fn.name}'"
                            )
        return SIRPassResult(success=len(errors) == 0, errors=errors)


class DeadCodeEliminationPass:
    """Identifica e remove instruções após return dentro do mesmo bloco básico."""
    def run(self, module: SIRModule) -> SIRPassResult:
        changed = False
        for fn in module.functions:
            for block in fn.blocks:
                new_instructions = []
                for inst in block.instructions:
                    new_instructions.append(inst)
                    if isinstance(inst, ReturnInst):
                        if len(block.instructions) > len(new_instructions):
                            changed = True
                        break  # Tudo após o return no mesmo bloco é inalcançável
                block.instructions = new_instructions
        return SIRPassResult(success=True, changed=changed)


class BranchFoldingPass:
    """Colapso de Ramos: Simplifica desvios condicionais redundantes e atalhos trampolim."""
    def run(self, module: SIRModule) -> SIRPassResult:
        changed = False
        for fn in module.functions:
            # 1. Identificar blocos trampolim (blocos que contêm apenas um BranchInst incondicional)
            trampolines: Dict[str, str] = {}
            for block in fn.blocks:
                if len(block.instructions) == 1 and isinstance(block.instructions[0], BranchInst):
                    target = block.instructions[0].target_block
                    if target != block.label:
                        trampolines[block.label] = target

            # Resolver trampolins em cadeia (A -> B -> C => A -> C)
            for src in list(trampolines.keys()):
                curr = trampolines[src]
                visited = {src}
                while curr in trampolines and curr not in visited:
                    visited.add(curr)
                    curr = trampolines[curr]
                trampolines[src] = curr

            # 2. Otimizar instruções de desvio
            for block in fn.blocks:
                new_instructions = []
                for inst in block.instructions:
                    if isinstance(inst, CondBranchInst):
                        true_t = trampolines.get(inst.true_block, inst.true_block)
                        false_t = trampolines.get(inst.false_block, inst.false_block)
                        # Se ambos os ramos vão para o mesmo alvo, transforma em salto incondicional
                        if true_t == false_t:
                            new_instructions.append(BranchInst(target_block=true_t))
                            changed = True
                        else:
                            if true_t != inst.true_block or false_t != inst.false_block:
                                inst.true_block = true_t
                                inst.false_block = false_t
                                changed = True
                            new_instructions.append(inst)
                    elif isinstance(inst, BranchInst):
                        new_target = trampolines.get(inst.target_block, inst.target_block)
                        if new_target != inst.target_block:
                            inst.target_block = new_target
                            changed = True
                        new_instructions.append(inst)
                    else:
                        new_instructions.append(inst)
                block.instructions = new_instructions

        return SIRPassResult(success=True, changed=changed)


class RedundantLoadPass:
    """Eliminação de Cargas Redundantes: detecta leituras imediatas de valores recém-armazenados."""
    def run(self, module: SIRModule) -> SIRPassResult:
        changed = False
        for fn in module.functions:
            for block in fn.blocks:
                slot_values: Dict[str, SIRValue] = {}
                alias_map: Dict[str, SIRValue] = {}
                new_instructions = []

                for inst in block.instructions:
                    # Chamadas de sistema ou funções externas podem ter efeitos colaterais de memória
                    if isinstance(inst, CallInst):
                        slot_values.clear()
                        new_instructions.append(inst)
                        continue

                    if isinstance(inst, StoreInst):
                        slot_values[inst.destination.name] = inst.source
                        new_instructions.append(inst)
                    elif isinstance(inst, LoadInst):
                        src_name = inst.source.name
                        if src_name in slot_values:
                            # O valor já reside no registrador virtual do store!
                            # Mapeamos o resultado do load para o valor de origem
                            alias_map[inst.result.name] = slot_values[src_name]
                            changed = True
                            # Mantemos a instrução no SIR para manter tipagem, mas com anotação/otimização
                            new_instructions.append(inst)
                        else:
                            new_instructions.append(inst)
                    else:
                        new_instructions.append(inst)

                block.instructions = new_instructions

        return SIRPassResult(success=True, changed=changed)


class UnreachableBlockPass:
    """Elimina blocos básicos inacessíveis a partir do bloco de entrada da função."""
    def run(self, module: SIRModule) -> SIRPassResult:
        changed = False
        for fn in module.functions:
            if not fn.blocks:
                continue
            entry_label = fn.blocks[0].label
            reachable: Set[str] = {entry_label}
            queue = [entry_label]
            block_map = {b.label: b for b in fn.blocks}

            while queue:
                curr_label = queue.pop(0)
                blk = block_map.get(curr_label)
                if not blk:
                    continue
                for inst in blk.instructions:
                    if isinstance(inst, BranchInst):
                        tgt = inst.target_block
                        if tgt not in reachable and tgt in block_map:
                            reachable.add(tgt)
                            queue.append(tgt)
                    elif isinstance(inst, CondBranchInst):
                        for tgt in (inst.true_block, inst.false_block):
                            if tgt not in reachable and tgt in block_map:
                                reachable.add(tgt)
                                queue.append(tgt)

            if len(reachable) < len(fn.blocks):
                fn.blocks = [b for b in fn.blocks if b.label in reachable]
                changed = True

        return SIRPassResult(success=True, changed=changed)


class HardwareInterruptEffectPass:
    """Reject forbidden effects reachable from interrupt handlers."""

    def run(self, module: SIRModule) -> SIRPassResult:
        errors = []
        forbidden = {
            "malloc", "heap_allocate", "alloc", "sleep", "block_on",
            "wait_for_event",
        }
        functions = {fn.name: fn for fn in module.functions}
        for fn in module.functions:
            if not (
                getattr(fn, "is_trap", False)
                or fn.name.startswith("trap_")
                or fn.name.startswith("isr_")
            ):
                continue

            pending = [(fn.name, (fn.name,))]
            visited = set()
            while pending:
                current_name, path = pending.pop(0)
                if current_name in visited:
                    continue
                visited.add(current_name)
                current = functions.get(current_name)
                if current is None:
                    continue
                for block in current.blocks:
                    for inst in block.instructions:
                        if isinstance(inst, AwaitInst):
                            chain = " -> ".join((*path, "await"))
                            errors.append(
                                f"sir effect error: efeito async proibido "
                                f"em contexto de interrupÃ§Ã£o '{fn.name}' "
                                f"(call chain: {chain})"
                            )
                            continue
                        if not isinstance(inst, CallInst):
                            continue
                        if (
                            inst.callee in forbidden
                            or _CALL_EFFECTS.get(inst.callee)
                            in {"alloc", "blocking"}
                        ):
                            chain = " -> ".join((*path, inst.callee))
                            errors.append(
                                f"sir effect error: operação proibida "
                                f"'{inst.callee}' em contexto de interrupção "
                                f"'{fn.name}' (call chain: {chain})"
                            )
                        elif inst.callee in functions and inst.callee not in visited:
                            pending.append(
                                (inst.callee, (*path, inst.callee))
                            )
                        elif inst.callee not in _CALL_EFFECTS:
                            chain = " -> ".join((*path, inst.callee))
                            errors.append(
                                f"sir effect error: chamada com efeitos "
                                f"desconhecidos '{inst.callee}' em contexto de "
                                f"interrupÃ§Ã£o '{fn.name}' "
                                f"(call chain: {chain})"
                            )
        return SIRPassResult(success=len(errors) == 0, errors=errors)


class BoundsCheckEliminationPass:
    """Eliminação de Checagem de Limites (Bounds Check Elimination — BCE):
    Analisa acessos indexados a arrays/fatias no SIR. Se uma verificação bounds_check
    já foi comprovada anteriormente no mesmo fluxo sem alteração de índice ou comprimento,
    ou se can_eliminate já é válido, marca a instrução como can_eliminate=True."""
    def run(self, module: SIRModule) -> SIRPassResult:
        changed = False
        for fn in module.functions:
            for block in fn.blocks:
                verified_bounds: Set[Tuple[str, str]] = set()
                new_instructions = []
                for inst in block.instructions:
                    if isinstance(inst, BoundsCheckInst):
                        key = (inst.index.name, inst.length.name)
                        if key in verified_bounds or inst.can_eliminate:
                            inst.can_eliminate = True
                            changed = True
                            new_instructions.append(inst)
                        else:
                            verified_bounds.add(key)
                            new_instructions.append(inst)
                    else:
                        new_instructions.append(inst)
                block.instructions = new_instructions
        return SIRPassResult(success=True, changed=changed)


class ArcOptimizationPass:
    """Eliminação de Pares Retain/Release de ARC:
    Se um objeto com contagem de referências sofre retain_value seguido de release_value
    sem escapar para outra função/thread (sem chamadas intermediárias que capturem o valor),
    ambas as operações atômicas são eliminadas do bloco."""
    def run(self, module: SIRModule) -> SIRPassResult:
        changed = False
        for fn in module.functions:
            for block in fn.blocks:
                i = 0
                while i < len(block.instructions):
                    inst = block.instructions[i]
                    if isinstance(inst, RetainInst):
                        val_name = inst.value.name
                        found_release_idx = -1
                        escaped = False
                        for j in range(i + 1, len(block.instructions)):
                            later = block.instructions[j]
                            if isinstance(later, ReleaseInst) and later.value.name == val_name:
                                found_release_idx = j
                                break
                            if isinstance(later, ReturnInst) and later.value and later.value.name == val_name:
                                escaped = True
                                break
                            if isinstance(later, CallInst) and any(arg.name == val_name for arg in later.arguments):
                                escaped = True
                                break
                        if found_release_idx != -1 and not escaped:
                            del block.instructions[found_release_idx]
                            del block.instructions[i]
                            changed = True
                            continue
                    i += 1
        return SIRPassResult(success=True, changed=changed)


class Mem2RegPass:
    """Mem2Reg com Nós Phi (phi-nodes):
    Promove variáveis locais alocadas no stack (AllocStackInst) para registradores
    virtuais SSA puros. Remove pares redundantes de alloc_stack/store/load e insere
    PhiInst nas junções de blocos convergentes."""
    def run(self, module: SIRModule) -> SIRPassResult:
        changed = False
        for fn in module.functions:
            stack_slots: Dict[str, AllocStackInst] = {}
            for block in fn.blocks:
                for inst in block.instructions:
                    if isinstance(inst, AllocStackInst):
                        stack_slots[inst.result.name] = inst

            if not stack_slots:
                continue

            block_defs: Dict[str, Dict[str, SIRValue]] = {}
            load_replacements: Dict[str, SIRValue] = {}

            for block in fn.blocks:
                curr_defs: Dict[str, SIRValue] = {}
                new_insts = []
                for inst in block.instructions:
                    if isinstance(inst, AllocStackInst):
                        changed = True
                        continue
                    elif isinstance(inst, StoreInst) and inst.destination.name in stack_slots:
                        curr_defs[inst.destination.name] = inst.source
                        changed = True
                    elif isinstance(inst, LoadInst) and inst.source.name in stack_slots:
                        slot = inst.source.name
                        if slot in curr_defs:
                            load_replacements[inst.result.name] = curr_defs[slot]
                            changed = True
                        else:
                            new_insts.append(inst)
                    else:
                        new_insts.append(inst)
                block_defs[block.label] = curr_defs
                block.instructions = new_insts

            if load_replacements:
                for block in fn.blocks:
                    for inst in block.instructions:
                        self._replace_value_uses(inst, load_replacements)

            preds: Dict[str, List[str]] = {b.label: [] for b in fn.blocks}
            for block in fn.blocks:
                for inst in block.instructions:
                    if isinstance(inst, BranchInst):
                        if inst.target_block in preds:
                            preds[inst.target_block].append(block.label)
                    elif isinstance(inst, CondBranchInst):
                        if inst.true_block in preds:
                            preds[inst.true_block].append(block.label)
                        if inst.false_block in preds:
                            preds[inst.false_block].append(block.label)

            for block in fn.blocks:
                p_list = preds.get(block.label, [])
                if len(p_list) >= 2:
                    for slot_name, alloc_inst in stack_slots.items():
                        incoming: List[Tuple[SIRValue, str]] = []
                        for p in p_list:
                            if p in block_defs and slot_name in block_defs[p]:
                                incoming.append((block_defs[p][slot_name], p))
                        if len(incoming) == len(p_list) and len(set(v.name for v, _ in incoming)) > 1:
                            phi_res = SIRValue(name=f"phi_{slot_name}_{block.label}", type_name=alloc_inst.type_name)
                            phi_inst = PhiInst(result=phi_res, incoming=incoming)
                            block.instructions.insert(0, phi_inst)
                            changed = True

        return SIRPassResult(success=True, changed=changed)

    def _replace_value_uses(self, inst: SIRInstruction, replacements: Dict[str, SIRValue]) -> None:
        if isinstance(inst, ReturnInst) and inst.value and inst.value.name in replacements:
            inst.value = replacements[inst.value.name]
        elif isinstance(inst, CallInst):
            inst.arguments = [replacements.get(a.name, a) for a in inst.arguments]
        elif isinstance(inst, CondBranchInst) and inst.condition.name in replacements:
            inst.condition = replacements[inst.condition.name]
        elif isinstance(inst, StoreInst):
            if inst.source.name in replacements:
                inst.source = replacements[inst.source.name]
        elif isinstance(inst, BoundsCheckInst):
            if inst.index.name in replacements:
                inst.index = replacements[inst.index.name]
            if inst.length.name in replacements:
                inst.length = replacements[inst.length.name]
        elif isinstance(inst, RetainInst) and inst.value.name in replacements:
            inst.value = replacements[inst.value.name]
        elif isinstance(inst, ReleaseInst) and inst.value.name in replacements:
            inst.value = replacements[inst.value.name]


class SIRPassManager:
    def __init__(self):
        self.passes = [
            DeadCodeEliminationPass(),
            DefiniteInitializationPass(),
            SystemCapabilitySafetyPass(),
            EffectInferencePass(),
            HardwareInterruptEffectPass(),
            BranchFoldingPass(),
            RedundantLoadPass(),
            UnreachableBlockPass(),
            BoundsCheckEliminationPass(),
            ArcOptimizationPass(),
            Mem2RegPass()
        ]

    def run_all(self, module: SIRModule) -> SIRPassResult:
        all_errors = []
        any_changed = False
        for p in self.passes:
            res = p.run(module)
            if not res.success:
                all_errors.extend(res.errors)
            if res.changed:
                any_changed = True
        return SIRPassResult(success=len(all_errors) == 0, errors=all_errors, changed=any_changed)
