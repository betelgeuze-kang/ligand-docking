from theory.branches.aromatic_logic import AromaticLogic
from theory.branches.cation_pi_logic import CationPiLogic
from theory.branches.chalcogen_bond_logic import ChalcogenBondLogic
from theory.branches.charge_transfer_logic import ChargeTransferLogic
from theory.branches.halogen_bond_logic import HalogenBondLogic
from theory.branches.hbond_logic import HbondLogic
from theory.branches.hydrophobic_logic import HydrophobicLogic
from theory.branches.pi_cation_logic import PiCationLogic
from theory.branches.salt_bridge_logic import SaltBridgeLogic
from theory.branches.stacking_logic import StackingLogic


class SaltBridgeSpecialist(SaltBridgeLogic):
    always_zero_output = True


class HydrophobicSpecialist(HydrophobicLogic):
    always_zero_output = True


class AromaticSpecialist(AromaticLogic):
    always_zero_output = True


class HBSpecialist(HbondLogic):
    always_zero_output = True


class ChargeTransferSpecialist(ChargeTransferLogic):
    always_zero_output = True


class PiCationSpecialist(PiCationLogic):
    always_zero_output = True


class CationPiSpecialist(CationPiLogic):
    always_zero_output = True


class HalogenBondSpecialist(HalogenBondLogic):
    always_zero_output = True


class ChalcogenBondSpecialist(ChalcogenBondLogic):
    always_zero_output = True


class StackingSpecialist(StackingLogic):
    always_zero_output = True
