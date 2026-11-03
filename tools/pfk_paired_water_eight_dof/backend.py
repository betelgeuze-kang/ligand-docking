"""Mobile-ligand WL admission around the caller-admitted original Torch kernel.

No pair potential is implemented here. The original water pair kernel owns all
energy/force arithmetic. The caller must admit that callable's exact source and
run this adapter in its own process, outside the dry evaluator's instrumentation.
An observer must durably acknowledge each reservation before numerical dispatch.
Any failure poisons this instance; unresolved work is never retried.
"""

from dataclasses import dataclass
import math
from collections.abc import Mapping
import threading
from types import MappingProxyType, SimpleNamespace

import torch


_GRAD = torch.autograd.grad
_GRAD_SCOPE = threading.Lock()
_SETTINGS = {
    "cutoff_angstrom": 10.0,
    "switch_start_angstrom": 8.0,
    "minimum_distance_angstrom": 0.35,
    "dielectric": 1.0,
    "screening_kappa_per_angstrom": 0.0,
    "receptor_block_size": 128,
    "mixing_rule": "lorentz_berthelot",
    "periodic": False,
}
_FIELDS = ("sigma_angstrom", "epsilon_kcal_per_mol", "charge_e")


class UnresolvedWaterWork(BaseException):
    """The observer or an interrupted dispatch cannot confirm completed work."""


@dataclass(frozen=True)
class _Parameter:
    sigma_angstrom: float
    epsilon_kcal_per_mol: float
    charge_e: float


@dataclass(frozen=True)
class WaterTermsResult:
    components: Mapping
    forces: torch.Tensor
    work: Mapping
    active_pairs: int

    @property
    def energy(self):
        return math.fsum(self.components.values())


def _parameters(rows):
    result = []
    for index, row in enumerate(rows):
        if isinstance(row, Mapping):
            if set(row) not in (set(_FIELDS), {*_FIELDS, "atom_index"}):
                raise ValueError("exact sigma/epsilon/charge parameter fields required")
            if "atom_index" in row and (type(row["atom_index"]) is not int or row["atom_index"] != index):
                raise ValueError("ordered parameter coverage required")
            values = [row[name] for name in _FIELDS]
        elif isinstance(row, (tuple, list)):
            if len(row) != 3:
                raise ValueError("three parameter values required")
            values = row
        else:
            if hasattr(row, "atom_index") and (type(row.atom_index) is not int or row.atom_index != index):
                raise ValueError("ordered parameter coverage required")
            values = [getattr(row, name) for name in _FIELDS]
        if any(isinstance(v, bool) or not isinstance(v, (int, float))
               or not math.isfinite(v) for v in values):
            raise ValueError("finite real parameters required")
        sigma, epsilon, charge = map(float, values)
        if not (0 <= sigma <= 100 and 0 <= epsilon <= 1e6 and abs(charge) <= 100):
            raise ValueError("parameter applicability exceeded")
        if sigma == 0 and epsilon != 0:
            raise ValueError("zero sigma requires zero epsilon")
        result.append(_Parameter(sigma, epsilon, charge))
    return tuple(result)


def _coordinates(value, count):
    if (not isinstance(value, torch.Tensor) or value.dtype != torch.float64
            or value.device.type != "cpu" or tuple(value.shape) != (count, 3)
            or not bool(torch.isfinite(value).all())):
        raise ValueError("finite CPU binary64 Nx3 coordinates required")
    return value.detach().clone()


class MobileLigandWaterTerms:
    def __init__(self, admitted_original_pair_kernel, ligand_parameters,
                 fixed_water_coordinates, fixed_water_parameters, pairsettings,
                 observer=None):
        if not callable(admitted_original_pair_kernel):
            raise ValueError("caller-admitted original pair kernel required")
        if observer is not None and not callable(observer):
            raise ValueError("callable work observer required")
        settings = dict(pairsettings) if isinstance(pairsettings, Mapping) else {
            name: getattr(pairsettings, name) for name in _SETTINGS
        }
        if settings != _SETTINGS or type(settings["receptor_block_size"]) is not int \
                or type(settings["periodic"]) is not bool:
            raise ValueError("original 10/8 angstrom nonperiodic pair settings required")
        if any(isinstance(settings[k], bool) or not isinstance(settings[k], (int, float))
               for k in _SETTINGS if k.endswith("angstrom") or k == "dielectric"):
            raise ValueError("real pair settings required")
        self._ligand = _parameters(ligand_parameters)
        self._water = _parameters(fixed_water_parameters)
        if not 1 <= len(self._ligand) <= 256 or not 3 <= len(self._water) <= 1086 \
                or len(self._water) % 3:
            raise ValueError("1..256 ligand sites and 1..362 complete OHH waters required")
        self._fixed = _coordinates(fixed_water_coordinates, len(self._water))
        self._reference = self._fixed.clone()
        self._frozen_parameters = self._parameter_values()
        self._kernel = admitted_original_pair_kernel
        self._observer = observer
        self._cross = SimpleNamespace(**settings, receptor_atoms=self._water)
        self._context = SimpleNamespace(
            receptor=SimpleNamespace(coordinates=self._fixed.unsqueeze(0), atom_count=len(self._water)),
            cross=self._cross, assert_intact=self._assert_intact,
        )
        self._active = False
        self._poisoned = False
        self._unknown = False
        self._counts = {
            kind: dict(reserved=0, dispatched=0, returned=0, failed=0, acknowledged=0, pending=0)
            for kind in ("WL_EF", "backward_WL")
        }

    @property
    def fixed_water_coordinates(self):
        return self._fixed.clone()

    def work_snapshot(self):
        kernels = self._counts["WL_EF"]["dispatched"]
        backwards = self._counts["backward_WL"]["dispatched"]
        return {"stages": {k: dict(v) for k, v in self._counts.items()},
                "total_work_known": not self._unknown,
                "known_kernel_calls": kernels,
                "total_kernel_calls": None if self._unknown else kernels,
                "known_backward_calls": backwards,
                "total_backward_calls": None if self._unknown else backwards,
                "poisoned": self._poisoned, "unknown_work_reissued": False}

    def _parameter_values(self):
        return tuple(tuple(tuple(getattr(p, name) for name in _FIELDS) for p in rows)
                     for rows in (self._ligand, self._water))

    def _assert_intact(self):
        if (not torch.equal(self._fixed, self._reference)
                or self._parameter_values() != self._frozen_parameters
                or vars(self._cross) != {**_SETTINGS, "receptor_atoms": self._water}
                or self._context.receptor.atom_count != len(self._water)
                or not torch.equal(self._context.receptor.coordinates[0], self._reference)):
            raise ValueError("fixed water coordinates/parameters/settings changed")

    def _notify(self, kind, event, success):
        try:
            if self._observer is not None:
                self._observer(kind, event, success)
        except BaseException as exc:
            self._unknown = self._poisoned = True
            raise UnresolvedWaterWork("work-observer durability is unresolved") from exc

    def _dispatch(self, kind, operation):
        row = self._counts[kind]
        row["reserved"] += 1
        row["pending"] += 1
        self._notify(kind, "started", None)
        row["dispatched"] += 1
        try:
            value = operation()
        except BaseException as exc:
            self._poisoned = True
            if not isinstance(exc, Exception) or self._unknown:
                self._unknown = True
                raise
            self._notify(kind, "finished", False)
            row["failed"] += 1
            row["pending"] -= 1
            raise
        row["returned"] += 1
        self._notify(kind, "finished", True)
        row["acknowledged"] += 1
        row["pending"] -= 1
        return value

    def evaluate(self, ligand_coordinates):
        if self._poisoned:
            raise RuntimeError("failed/unknown WL adapter cannot be retried")
        coordinates = _coordinates(ligand_coordinates, len(self._ligand))
        try:
            self._assert_intact()
        except BaseException:
            self._poisoned = True
            raise
        if self._active or not _GRAD_SCOPE.acquire(blocking=False):
            raise RuntimeError("overlapping WL instrumentation forbidden")
        before = self.work_snapshot()
        self._active = True
        installed = False
        owner = threading.get_ident()
        backwards = 0

        def counted_grad(*args, **kwargs):
            nonlocal backwards
            if threading.get_ident() != owner:
                raise RuntimeError("foreign thread entered WL instrumentation")
            if backwards >= math.ceil(len(self._water) / 128):
                raise RuntimeError("original WL receptor-block backward cap exceeded")
            backwards += 1
            return self._dispatch("backward_WL", lambda: _GRAD(*args, **kwargs))

        try:
            if torch.autograd.grad is not _GRAD:
                raise RuntimeError("dry/foreign autograd instrumentation overlaps WL")
            torch.autograd.grad = counted_grad
            installed = True

            def evaluate_original():
                components, forces, active = self._kernel(
                    self._context, SimpleNamespace(coordinates=coordinates.unsqueeze(0)), self._ligand,
                )
                self._assert_intact()
                if set(components) != {"cross_lennard_jones", "cross_screened_coulomb"}:
                    raise ValueError("original WL component contract changed")
                values = {}
                for source, target in (("cross_lennard_jones", "WL_LJ"),
                                       ("cross_screened_coulomb", "WL_Coulomb")):
                    value = components[source]
                    if (not isinstance(value, torch.Tensor) or value.dtype != torch.float64
                            or value.device.type != "cpu" or tuple(value.shape) != (1,)
                            or not bool(torch.isfinite(value).all())):
                        raise ValueError("finite original WL component required")
                    values[target] = float(value[0])
                force = _coordinates(forces[0], len(self._ligand))
                if forces.shape != (1, len(self._ligand), 3) or type(active) is not int \
                        or not 0 <= active <= len(self._ligand) * len(self._water):
                    raise ValueError("original WL force/pair census changed")
                return values, force, active

            values, forces, active = self._dispatch("WL_EF", evaluate_original)
            if torch.autograd.grad is not counted_grad:
                self._unknown = True
                raise RuntimeError("WL autograd instrumentation changed during dispatch")
            prior = before["stages"]
            work = {"kernel_calls": self._counts["WL_EF"]["dispatched"] - prior["WL_EF"]["dispatched"],
                    "backward_calls": self._counts["backward_WL"]["dispatched"] - prior["backward_WL"]["dispatched"],
                    "total_work_known": True, "unknown_work_reissued": False}
            return WaterTermsResult(MappingProxyType(values), forces, MappingProxyType(work), active)
        except BaseException:
            self._poisoned = True
            raise
        finally:
            if installed:
                torch.autograd.grad = _GRAD
            self._active = False
            _GRAD_SCOPE.release()
