use std::fmt;

use crate::native_hash::CanonicalHash;
use crate::{
    native_fixed64_coordinate_sha256, native_fixed64_heavy_atom_mask_sha256,
    native_fixed64_radii_sha256, Fixed64Allocation, Fixed64AtomicFeatureEvidence,
    Fixed64ExactV11SourceEvidence, Fixed64FeatureInventory, Fixed64FeatureKind,
    Fixed64IndexedSourceEvidence, Fixed64SourceEvidence, Vec3,
};

pub const REPOSITORY_D0_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_repository_synthetic_d0_native_source/1.0.0";
pub const REPOSITORY_D0_PROFILE_ID: &str =
    "betelgeuze.engine_v2_repository_synthetic_d0_fixed64_source/native-1.0.0";
pub const REPOSITORY_D0_CANDIDATE_DENOMINATOR: usize = 64;
pub const REPOSITORY_D0_LIGAND_ATOM_COUNT: usize = 5;
pub const REPOSITORY_D0_RECEPTOR_ATOM_COUNT: usize = 5;
pub const REPOSITORY_D0_TOP_K: usize = 5;
pub const REPOSITORY_D0_SEED: u64 = 4_301;
pub const REPOSITORY_D0_POCKET_RADIUS_ANGSTROM: f64 = 10.0;
pub const REPOSITORY_D0_TRANSLATION_RADIUS_ANGSTROM: f64 = 4.0;
pub const REPOSITORY_D0_CENTERED_CANDIDATE_COUNT: usize = 8;
pub const REPOSITORY_D0_GUIDED_SOURCE_INDICES: [u32; 16] = [
    24, 27, 29, 32, 34, 37, 40, 42, 45, 47, 50, 53, 55, 58, 60, 63,
];
pub const REPOSITORY_D0_RETAINED_SOURCE_INDICES: [u32; 4] = [36, 45, 54, 63];
pub const REPOSITORY_D0_EXPECTED_BUNDLE_SHA256: [u8; 32] =
    digest("929eedd01ef06fe28daa362654325aa5f849891b58d3d6d67a161a8f43fda37a");
pub const REPOSITORY_D0_EXPECTED_PREPARED_INPUT_SHA256: [u8; 32] =
    digest("9365608f04170392497222d4681e7494c2ddedb01fcab653ca1aded4de984e6e");
pub const REPOSITORY_D0_EXPECTED_FEATURE_INVENTORY_SHA256: [u8; 32] =
    digest("44cdd65dfa69fd58fdfd9a174cebf56d17a2be71ded0893c9a503e67fd42179e");
pub const REPOSITORY_D0_EXPECTED_ALLOCATION_SHA256: [u8; 32] =
    digest("8775a56bcd15bc903ead9365eb699c167d523157404dc2271c11a5274bacd2fb");

const REQUEST_SHA256: [u8; 32] =
    digest("bbf826bbdc30818f27c95f04763696bd09b7aa3e9cbd75c5d1597442d8129629");
const LIGAND_SYSTEM_SHA256: [u8; 32] =
    digest("62dc8387fc033b9f87c1a6f5d97ed8f2e897e5c1332e8d6567faf5ea06000353");
const RECEPTOR_SYSTEM_SHA256: [u8; 32] =
    digest("f205331ddce5591aeaac950a32a4e1cc151b1adf92793d6095e1cd226cfdd913");
const AUTHORITY_INPUT_RECEIPT_SHA256: [u8; 32] =
    digest("8b434dd9b208c57f0be6f77442d6e041f6ca1a1727409bcf3fd43716b13a4284");
const LEGACY_GUIDED_POLICY_SHA256: [u8; 32] =
    digest("2974e9ba80479cccc97dce1b51567e8e7309e7f89c983401c9a8966a3d08633f");
const LEGACY_GUIDED_RECEIPT_SHA256: [u8; 32] =
    digest("8fc7cd2c744793fa9a000e6aab7b94e95aa19a2e8d74dda2b5468d2922d512c6");

const LIGAND_PREPARED_COORDINATES: [Vec3; REPOSITORY_D0_LIGAND_ATOM_COUNT] = [
    Vec3::new(-2.0, 1.0, 0.0),
    Vec3::new(-1.0, 0.0, 0.0),
    Vec3::new(0.0, 0.0, 0.0),
    Vec3::new(-2.0, 0.0, 0.0),
    Vec3::new(-3.0, 0.0, 0.0),
];
const RECEPTOR_COORDINATES: [Vec3; REPOSITORY_D0_RECEPTOR_ATOM_COUNT] = [
    Vec3::new(2.0, 0.0, 0.0),
    Vec3::new(3.0, 3.0, 0.0),
    Vec3::new(2.5, 2.5, 0.0),
    Vec3::new(-2.0, 3.0, 0.0),
    Vec3::new(6.0, 6.0, 0.0),
];
const LIGAND_VDW_RADII: [f64; REPOSITORY_D0_LIGAND_ATOM_COUNT] = [1.70, 1.55, 1.20, 1.52, 1.20];
const RECEPTOR_VDW_RADII: [f64; REPOSITORY_D0_RECEPTOR_ATOM_COUNT] = [1.52, 1.55, 1.20, 1.70, 1.20];
const LIGAND_ATOMIC_NUMBERS: [u8; REPOSITORY_D0_LIGAND_ATOM_COUNT] = [6, 7, 1, 8, 1];
const RECEPTOR_ATOMIC_NUMBERS: [u8; REPOSITORY_D0_RECEPTOR_ATOM_COUNT] = [8, 7, 1, 6, 1];
const LIGAND_PARTIAL_CHARGES: [f64; REPOSITORY_D0_LIGAND_ATOM_COUNT] = [0.0, -0.2, 0.2, -0.4, 0.4];
const RECEPTOR_PARTIAL_CHARGES: [f64; REPOSITORY_D0_RECEPTOR_ATOM_COUNT] =
    [-0.4, -0.2, 0.2, 0.0, 0.4];
const LIGAND_BONDS: [(usize, usize); 4] = [(0, 1), (1, 2), (0, 3), (3, 4)];
const RECEPTOR_BONDS: [(usize, usize); 1] = [(1, 2)];
const LIGAND_DONOR_ATOM_INDICES: [usize; 2] = [1, 3];
const LIGAND_ACCEPTOR_ATOM_INDICES: [usize; 2] = [1, 3];
const RECEPTOR_DONOR_ATOM_INDICES: [usize; 1] = [1];
const RECEPTOR_ACCEPTOR_ATOM_INDICES: [usize; 2] = [0, 1];
const PARTIAL_CHARGE_SITE_THRESHOLD: f64 = 0.25;

const V7_LEGACY_PROPOSAL_SHA256: [[u8; 32]; 24] = [
    digest("966ee9746526ecc129d054da219e008eafcacee1f60233ec1d7905c4d8ca26e5"),
    digest("23735e47f8f059d7725749d636ea799ac1382edd1cf61dc93c965036727d9f07"),
    digest("0baa0d5c22af14ea9edc2084ea020c74f7d51c6a93683018f7b5e6b73097d59a"),
    digest("9e243ab34d375b9f4f1dfeca6f8bad9a790783824d01a3fb641594851e2720bd"),
    digest("d2f0c724dfe537d64b9420821bd612230b102abfdf6d862a03a00bc633910205"),
    digest("2334cb0478439b5b9a16a7fa5d9a17af15dd23c649a5704bc115e8d8de0932e3"),
    digest("95c05e1a87a8cc8b04ba6c9062eba65e166ad744a58c5d509c7f305fc647b348"),
    digest("afc0f69a7bf51f01838ee6241ea4af7ba2d478a034d2ca9a5cf4347a5c491fa7"),
    digest("f8c99a8807340c676972266795a64add0c98090e8965793448ddf5dbdf2cd7ca"),
    digest("7acadc3ada830b1c701f9a967b8efdeb68d1b2cd251ba90ff8baa9901dfa5dae"),
    digest("2faa9b77675af683c6d5f00565a682511484e842a05908a1532edf3a0f1d660d"),
    digest("92fcc95be62c6c39c1cecec41e5f1f008128d673a21bd718d1caf8119dd924c8"),
    digest("6ebb7a3e1ecbfbdb9cd0efe0d5c533ef67a6355299c4f9fd8b81b1e7b6c79581"),
    digest("f501252514bc1e32506ddda5c4f4d36c2bce33ab0390fbceb12305443efbbbb8"),
    digest("87684b72cde2661fdfe8e180f61df0028b7978be706b5fa49c1b4ee6f5632632"),
    digest("7c35beb2b8abc08a494660a6d42587a2506fb7b07cf16f4d10ab7fc9fdeeb712"),
    digest("6e85f4e638265d0105b6e0211258d3e3e2e0d538fbd6df2bfbb1657f798e7a80"),
    digest("1455898edc4a8edaa603e9e866f5901f0377b6192a6d873bb81ec6188ec9a7bf"),
    digest("c3efc785897892f72af22b11340073f1094d8edc1fcaf99d2696de508908ecbf"),
    digest("d87f8677841fd9bef12bf434cb7e383a912494b341fe86d0dc3c7601a513daa7"),
    digest("68c10d2b1bdf19acb8d9b3a1d910cc490ca4bc3eba3cfaa1da112466f65b266c"),
    digest("c3160daa64696096ecd40e2eb259a523845564d7f0d00566eee9aaf585fb68ed"),
    digest("14ea934e475c1467907080073e4464c1b98cc4406dc4cdee9b6886604f1050b1"),
    digest("d0963802c3e9d47c69a83210bd01577aa9245d043506848e60bc064377264ebd"),
];

const RETAINED_LEGACY_PROPOSAL_SHA256: [[u8; 32]; 4] = [
    digest("30dbc54c75a39097a1169688adb1dc2b8db651db1e3cd3b07e240b0e04c1559a"),
    digest("4475285908730c9dfc62210cccfbd1784675d72b6d31bf9eff724fb019412bf2"),
    digest("0d47998be65359b2fbd263a71874678ce02f947944d3db4a365312a051dc2d42"),
    digest("95c156b3780d547ca2b88577415ffe32ee27735a1b7d2f756c0323189c707559"),
];

const V7_LEGACY_NATIVE_COORDINATE_SHA256: [[u8; 32]; 24] = [
    digest("9b39f3d5b4d6b4d8da17abfc5ce717bc45e271ab18a01dd9113068cb79300d0e"),
    digest("6e111f368c8798885ecfd228571b09b918cb3642fa8ffd17ba804a432f9e5064"),
    digest("f188122aa0480d4a9742e2889be51f5a3065b36835d1d47f82afcfeff9fbe686"),
    digest("8aa43bc8326a2dc56bc44881076c225decf4ba1bae904db67b924ca7cb60820f"),
    digest("e6ad7be114a9201c178418c0637865d949a9a0c3b4a411c6b9669235a22d0606"),
    digest("afcbcf66f52d58e95f259df7ec8c485c2a20c58a270db5ea49bf96abfedc5627"),
    digest("2bb06056ee212d9e67e30f8efc0936838b06f49cdb04e7b0f1efdecc787553e4"),
    digest("bbd776d33936907a5361db0e0da20e018642744cf1dd8280279bdcc3363f00df"),
    digest("93887f0605a124ba4be66e0f04ce5ac1b45125628aa6df40f3cbdbe7c8c4a9fb"),
    digest("ea96c427f62fd5955acb1e4f073fd10f78e3e97cc8fa2745ccfcc34fe38c426d"),
    digest("61b9afebc988cd7287c1e73b1cb85ea3863d532755044f91cad5e122569a5df9"),
    digest("ab2dc6958cdf6953fa6339f89536aa9039ba4617d202d282e8596eeb6175c68f"),
    digest("b273eb55c92d0a0ef8779ddc6d63f83bc790836778569596c9a4ba62125b42b5"),
    digest("1bb7b596aa7dbca1f43154c2f53c00b849efddbdfaa8b6884751a513d2529cd3"),
    digest("11da55b52be36e6920b703aa958f75d3431e5e68e5271b3fadbdbd12c9640917"),
    digest("175d8c75beec6acf0eb12f4695f7046e04d30057444c9f0a967ced617483651e"),
    digest("d03cacd1a5d5bdf312ab31966d0b0368fa2dd738e3d891a1fa0a1ccf7751774b"),
    digest("ed543a81270e015b766ca4d5a4565973fdcb06535011e5d3bd7a243b2d148ecf"),
    digest("4d0ffe7eb5dc0940b30f21f885caf648adb58b50acf9d5edeec38c35e793e754"),
    digest("76189ad01f9bc509074b2655f5673080aeaa9b6ff4680356993a4f199a9324ed"),
    digest("418f961cbf00822a3fa3832d9a933c3538822cc9e78166bbae556ded38899999"),
    digest("07efccb9213e09356cea68e27b5eae18d756bddb1d31643520074b8c09438fc5"),
    digest("b8d06e47c13296f87f0a00e3f2cc6ee65158fddfb2dc18708876e1887359ab9d"),
    digest("fdbbf85a652ccb71ce25031d485568332d00882613fc153e9905608bc4e6bb84"),
];

const RETAINED_LEGACY_NATIVE_COORDINATE_SHA256: [[u8; 32]; 4] = [
    digest("48afedc1bde53db93dc13da3c203dd8827864d0edcdeeddb05b14d8955157313"),
    digest("d03cacd1a5d5bdf312ab31966d0b0368fa2dd738e3d891a1fa0a1ccf7751774b"),
    digest("7f017254e8a9f45c7ea31363f45631c68c854df8aee7a4b3f7783519855ff6a7"),
    digest("fdbbf85a652ccb71ce25031d485568332d00882613fc153e9905608bc4e6bb84"),
];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum SourceRole {
    Exact,
    V7Control,
    RetainedControl,
}

impl SourceRole {
    const fn tag(self) -> u8 {
        match self {
            Self::Exact => 0,
            Self::V7Control => 1,
            Self::RetainedControl => 2,
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct RepositoryD0ProposalSource {
    source_index: u32,
    upstream_uniform_source_index: u32,
    coordinates_angstrom: [Vec3; REPOSITORY_D0_LIGAND_ATOM_COUNT],
    rotation: [[f64; 3]; 3],
    translation_angstrom: Vec3,
    legacy_proposal_sha256: [u8; 32],
    coordinate_sha256: [u8; 32],
    source_receipt_sha256: [u8; 32],
}

impl RepositoryD0ProposalSource {
    #[must_use]
    pub const fn source_index(&self) -> u32 {
        self.source_index
    }

    #[must_use]
    pub const fn upstream_uniform_source_index(&self) -> u32 {
        self.upstream_uniform_source_index
    }

    #[must_use]
    pub const fn coordinates_angstrom(&self) -> &[Vec3; REPOSITORY_D0_LIGAND_ATOM_COUNT] {
        &self.coordinates_angstrom
    }

    #[must_use]
    pub const fn rotation(&self) -> &[[f64; 3]; 3] {
        &self.rotation
    }

    #[must_use]
    pub const fn translation_angstrom(&self) -> Vec3 {
        self.translation_angstrom
    }

    #[must_use]
    pub const fn legacy_proposal_sha256(&self) -> [u8; 32] {
        self.legacy_proposal_sha256
    }

    #[must_use]
    pub const fn coordinate_sha256(&self) -> [u8; 32] {
        self.coordinate_sha256
    }

    #[must_use]
    pub const fn source_receipt_sha256(&self) -> [u8; 32] {
        self.source_receipt_sha256
    }

    #[must_use]
    pub const fn source_evidence(&self) -> Fixed64SourceEvidence {
        Fixed64SourceEvidence {
            receipt_sha256: self.source_receipt_sha256,
            proposal_sha256: self.legacy_proposal_sha256,
            coordinate_sha256: self.coordinate_sha256,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RepositoryD0AtomicFeature {
    kind: Fixed64FeatureKind,
    atom_indices: Vec<u64>,
    allocation_feature_receipt_sha256: [u8; 32],
    feature_geometry_receipt_sha256: [u8; 32],
}

impl RepositoryD0AtomicFeature {
    #[must_use]
    pub const fn kind(&self) -> Fixed64FeatureKind {
        self.kind
    }

    #[must_use]
    pub fn atom_indices(&self) -> &[u64] {
        &self.atom_indices
    }

    #[must_use]
    pub const fn allocation_feature_receipt_sha256(&self) -> [u8; 32] {
        self.allocation_feature_receipt_sha256
    }

    #[must_use]
    pub const fn feature_geometry_receipt_sha256(&self) -> [u8; 32] {
        self.feature_geometry_receipt_sha256
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct RepositoryD0SourceBundle {
    exact_source: RepositoryD0ProposalSource,
    v7_control_sources: [RepositoryD0ProposalSource; 24],
    retained_sources: [RepositoryD0ProposalSource; 4],
    atomic_features: Vec<RepositoryD0AtomicFeature>,
    prepared_input_receipt_sha256: [u8; 32],
    feature_geometry_inventory_sha256: [u8; 32],
    pocket_normal: Vec3,
    receipt_sha256: [u8; 32],
}

impl RepositoryD0SourceBundle {
    #[must_use]
    pub const fn request_sha256(&self) -> [u8; 32] {
        REQUEST_SHA256
    }

    #[must_use]
    pub const fn authority_input_receipt_sha256(&self) -> [u8; 32] {
        AUTHORITY_INPUT_RECEIPT_SHA256
    }

    #[must_use]
    pub const fn ligand_system_sha256(&self) -> [u8; 32] {
        LIGAND_SYSTEM_SHA256
    }

    #[must_use]
    pub const fn receptor_system_sha256(&self) -> [u8; 32] {
        RECEPTOR_SYSTEM_SHA256
    }

    #[must_use]
    pub const fn ligand_prepared_coordinates_angstrom(
        &self,
    ) -> &[Vec3; REPOSITORY_D0_LIGAND_ATOM_COUNT] {
        &LIGAND_PREPARED_COORDINATES
    }

    #[must_use]
    pub const fn receptor_coordinates_angstrom(
        &self,
    ) -> &[Vec3; REPOSITORY_D0_RECEPTOR_ATOM_COUNT] {
        &RECEPTOR_COORDINATES
    }

    #[must_use]
    pub const fn ligand_vdw_radii_angstrom(&self) -> &[f64; REPOSITORY_D0_LIGAND_ATOM_COUNT] {
        &LIGAND_VDW_RADII
    }

    #[must_use]
    pub const fn receptor_vdw_radii_angstrom(&self) -> &[f64; REPOSITORY_D0_RECEPTOR_ATOM_COUNT] {
        &RECEPTOR_VDW_RADII
    }

    #[must_use]
    pub const fn ligand_atomic_numbers(&self) -> &[u8; REPOSITORY_D0_LIGAND_ATOM_COUNT] {
        &LIGAND_ATOMIC_NUMBERS
    }

    #[must_use]
    pub const fn receptor_atomic_numbers(&self) -> &[u8; REPOSITORY_D0_RECEPTOR_ATOM_COUNT] {
        &RECEPTOR_ATOMIC_NUMBERS
    }

    #[must_use]
    pub const fn ligand_partial_charges_elementary(
        &self,
    ) -> &[f64; REPOSITORY_D0_LIGAND_ATOM_COUNT] {
        &LIGAND_PARTIAL_CHARGES
    }

    #[must_use]
    pub const fn receptor_partial_charges_elementary(
        &self,
    ) -> &[f64; REPOSITORY_D0_RECEPTOR_ATOM_COUNT] {
        &RECEPTOR_PARTIAL_CHARGES
    }

    #[must_use]
    pub const fn ligand_bonds(&self) -> &[(usize, usize); 4] {
        &LIGAND_BONDS
    }

    #[must_use]
    pub const fn receptor_bonds(&self) -> &[(usize, usize); 1] {
        &RECEPTOR_BONDS
    }

    #[must_use]
    pub fn ligand_heavy_atom_mask(&self) -> [bool; REPOSITORY_D0_LIGAND_ATOM_COUNT] {
        LIGAND_ATOMIC_NUMBERS.map(|atomic_number| atomic_number != 1)
    }

    #[must_use]
    pub const fn pocket_center_angstrom(&self) -> Vec3 {
        Vec3::new(0.0, 0.0, 0.0)
    }

    #[must_use]
    pub const fn pocket_radius_angstrom(&self) -> f64 {
        REPOSITORY_D0_POCKET_RADIUS_ANGSTROM
    }

    #[must_use]
    pub const fn exact_source(&self) -> &RepositoryD0ProposalSource {
        &self.exact_source
    }

    #[must_use]
    pub const fn v7_control_sources(&self) -> &[RepositoryD0ProposalSource; 24] {
        &self.v7_control_sources
    }

    #[must_use]
    pub const fn retained_sources(&self) -> &[RepositoryD0ProposalSource; 4] {
        &self.retained_sources
    }

    #[must_use]
    pub fn atomic_features(&self) -> &[RepositoryD0AtomicFeature] {
        &self.atomic_features
    }

    #[must_use]
    pub const fn prepared_input_receipt_sha256(&self) -> [u8; 32] {
        self.prepared_input_receipt_sha256
    }

    #[must_use]
    pub const fn feature_geometry_inventory_sha256(&self) -> [u8; 32] {
        self.feature_geometry_inventory_sha256
    }

    #[must_use]
    pub const fn pocket_normal(&self) -> Vec3 {
        self.pocket_normal
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    pub fn feature_inventory(&self) -> Result<Fixed64FeatureInventory, RepositoryD0SourceError> {
        let exact = Fixed64ExactV11SourceEvidence {
            source_receipt_sha256: self.exact_source.source_receipt_sha256,
            proposal_sha256: self.exact_source.legacy_proposal_sha256,
            ligand_coordinate_sha256: self.exact_source.coordinate_sha256,
            receptor_coordinate_sha256: native_fixed64_coordinate_sha256(&RECEPTOR_COORDINATES)
                .map_err(|_| {
                    RepositoryD0SourceError::InternalInvariant(
                        "repository D0 receptor coordinate identity is invalid",
                    )
                })?,
            prepared_ligand_topology_sha256: LIGAND_SYSTEM_SHA256,
            prepared_receptor_topology_sha256: RECEPTOR_SYSTEM_SHA256,
            ligand_vdw_radii_sha256: native_fixed64_radii_sha256(&LIGAND_VDW_RADII).map_err(
                |_| {
                    RepositoryD0SourceError::InternalInvariant(
                        "repository D0 ligand radii identity is invalid",
                    )
                },
            )?,
            ligand_heavy_atom_mask_sha256: native_fixed64_heavy_atom_mask_sha256(
                &self.ligand_heavy_atom_mask(),
            )
            .map_err(|_| {
                RepositoryD0SourceError::InternalInvariant(
                    "repository D0 ligand heavy-atom identity is invalid",
                )
            })?,
            receptor_vdw_radii_sha256: native_fixed64_radii_sha256(&RECEPTOR_VDW_RADII).map_err(
                |_| {
                    RepositoryD0SourceError::InternalInvariant(
                        "repository D0 receptor radii identity is invalid",
                    )
                },
            )?,
        };
        let atomic_features = self
            .atomic_features
            .iter()
            .map(|feature| Fixed64AtomicFeatureEvidence {
                kind: feature.kind,
                receipt_sha256: feature.allocation_feature_receipt_sha256,
            })
            .collect();
        let v7_control_sources = self
            .v7_control_sources
            .iter()
            .map(|source| Fixed64IndexedSourceEvidence {
                source_index: source.source_index,
                source: source.source_evidence(),
            })
            .collect();
        let retained_sources = self
            .retained_sources
            .iter()
            .map(|source| Fixed64IndexedSourceEvidence {
                source_index: source.source_index,
                source: source.source_evidence(),
            })
            .collect();
        Fixed64FeatureInventory::new(
            exact,
            atomic_features,
            v7_control_sources,
            Vec::new(),
            retained_sources,
        )
        .map_err(|_| {
            RepositoryD0SourceError::InternalInvariant(
                "repository D0 native feature inventory is invalid",
            )
        })
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RepositoryD0SourceError {
    InternalInvariant(&'static str),
}

impl fmt::Display for RepositoryD0SourceError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InternalInvariant(message) => {
                write!(
                    formatter,
                    "repository synthetic D0 source invariant failed: {message}"
                )
            }
        }
    }
}

impl std::error::Error for RepositoryD0SourceError {}

pub fn materialize_repository_synthetic_d0_sources(
) -> Result<RepositoryD0SourceBundle, RepositoryD0SourceError> {
    let baseline =
        std::array::from_fn::<_, REPOSITORY_D0_CANDIDATE_DENOMINATOR, _>(baseline_proposal);
    let v7_control_sources: [RepositoryD0ProposalSource; 24] = (0..24)
        .map(|index| {
            let upstream = if index < REPOSITORY_D0_CENTERED_CANDIDATE_COUNT {
                index
            } else {
                REPOSITORY_D0_GUIDED_SOURCE_INDICES[index - REPOSITORY_D0_CENTERED_CANDIDATE_COUNT]
                    as usize
            };
            source(
                SourceRole::V7Control,
                index as u32,
                upstream as u32,
                &baseline[upstream],
                V7_LEGACY_PROPOSAL_SHA256[index],
            )
        })
        .collect::<Result<Vec<_>, _>>()?
        .try_into()
        .map_err(|_| {
            RepositoryD0SourceError::InternalInvariant(
                "repository D0 V7 control denominator changed",
            )
        })?;
    let retained_sources: [RepositoryD0ProposalSource; 4] = (0..4)
        .map(|index| {
            let source_index = REPOSITORY_D0_RETAINED_SOURCE_INDICES[index];
            source(
                SourceRole::RetainedControl,
                source_index,
                source_index,
                &baseline[source_index as usize],
                RETAINED_LEGACY_PROPOSAL_SHA256[index],
            )
        })
        .collect::<Result<Vec<_>, _>>()?
        .try_into()
        .map_err(|_| {
            RepositoryD0SourceError::InternalInvariant(
                "repository D0 retained-source denominator changed",
            )
        })?;
    if v7_control_sources
        .iter()
        .zip(V7_LEGACY_NATIVE_COORDINATE_SHA256)
        .any(|(source, expected)| source.coordinate_sha256 != expected)
        || retained_sources
            .iter()
            .zip(RETAINED_LEGACY_NATIVE_COORDINATE_SHA256)
            .any(|(source, expected)| source.coordinate_sha256 != expected)
    {
        return Err(RepositoryD0SourceError::InternalInvariant(
            "native coordinates do not match the frozen current-V7 source identities",
        ));
    }
    let exact_source = source(
        SourceRole::Exact,
        0,
        0,
        &baseline[0],
        V7_LEGACY_PROPOSAL_SHA256[0],
    )?;
    let atomic_features = atomic_features(exact_source.source_receipt_sha256)?;
    let prepared_input_receipt_sha256 = prepared_input_sha256();
    let feature_geometry_inventory_sha256 = feature_inventory_sha256(&atomic_features);
    let pocket_normal = pocket_normal()?;
    let receipt_sha256 = bundle_sha256(
        &exact_source,
        &v7_control_sources,
        &retained_sources,
        &atomic_features,
        prepared_input_receipt_sha256,
        feature_geometry_inventory_sha256,
        pocket_normal,
    );
    let value = RepositoryD0SourceBundle {
        exact_source,
        v7_control_sources,
        retained_sources,
        atomic_features,
        prepared_input_receipt_sha256,
        feature_geometry_inventory_sha256,
        pocket_normal,
        receipt_sha256,
    };
    let inventory = value.feature_inventory()?;
    if bundle_sha256(
        &value.exact_source,
        &value.v7_control_sources,
        &value.retained_sources,
        &value.atomic_features,
        value.prepared_input_receipt_sha256,
        value.feature_geometry_inventory_sha256,
        value.pocket_normal,
    ) != value.receipt_sha256
        || value.receipt_sha256 != REPOSITORY_D0_EXPECTED_BUNDLE_SHA256
        || value.prepared_input_receipt_sha256 != REPOSITORY_D0_EXPECTED_PREPARED_INPUT_SHA256
        || value.feature_geometry_inventory_sha256
            != REPOSITORY_D0_EXPECTED_FEATURE_INVENTORY_SHA256
    {
        return Err(RepositoryD0SourceError::InternalInvariant(
            "repository D0 source receipts changed from the frozen native identities",
        ));
    }
    let allocation = Fixed64Allocation::build(inventory).map_err(|_| {
        RepositoryD0SourceError::InternalInvariant(
            "repository D0 fixed64 allocation cannot be derived",
        )
    })?;
    if allocation.receipt_sha256() != REPOSITORY_D0_EXPECTED_ALLOCATION_SHA256
        || allocation.ready_count() != 54
        || allocation.typed_failure_count() != 10
        || allocation.result_dependent_allocation()
        || allocation.molecular_execution_authorized()
    {
        return Err(RepositoryD0SourceError::InternalInvariant(
            "repository D0 fixed64 allocation changed from its frozen non-authoritative identity",
        ));
    }
    Ok(value)
}

#[derive(Clone, Copy)]
struct BaselineProposal {
    coordinates_angstrom: [Vec3; REPOSITORY_D0_LIGAND_ATOM_COUNT],
    rotation: [[f64; 3]; 3],
    translation_angstrom: Vec3,
}

fn baseline_proposal(proposal_index: usize) -> BaselineProposal {
    let centroid = centroid(&LIGAND_PREPARED_COORDINATES);
    let centered = LIGAND_PREPARED_COORDINATES.map(|point| point.minus(centroid));
    let rotation = haar_rotation(proposal_index);
    let offset = if proposal_index < REPOSITORY_D0_CENTERED_CANDIDATE_COUNT {
        Vec3::default()
    } else {
        spherical_offset(proposal_index)
    };
    let coordinates_angstrom = centered.map(|point| rotate(rotation, point).plus(offset));
    let translation_angstrom = offset.minus(rotate(rotation, centroid));
    BaselineProposal {
        coordinates_angstrom,
        rotation,
        translation_angstrom,
    }
}

fn source(
    role: SourceRole,
    source_index: u32,
    upstream_uniform_source_index: u32,
    baseline: &BaselineProposal,
    legacy_proposal_sha256: [u8; 32],
) -> Result<RepositoryD0ProposalSource, RepositoryD0SourceError> {
    let coordinate_sha256 = native_fixed64_coordinate_sha256(&baseline.coordinates_angstrom)
        .map_err(|_| {
            RepositoryD0SourceError::InternalInvariant(
                "repository D0 source coordinates are outside the native safety envelope",
            )
        })?;
    let mut hash = CanonicalHash::new("betelgeuze.repository_d0_source/native-v1");
    hash.byte(role.tag());
    hash.u32(source_index);
    hash.u32(upstream_uniform_source_index);
    hash.digest(REQUEST_SHA256);
    hash.digest(AUTHORITY_INPUT_RECEIPT_SHA256);
    hash.digest(LEGACY_GUIDED_POLICY_SHA256);
    hash.digest(LEGACY_GUIDED_RECEIPT_SHA256);
    hash.digest(legacy_proposal_sha256);
    hash.digest(coordinate_sha256);
    hash.bool(false);
    Ok(RepositoryD0ProposalSource {
        source_index,
        upstream_uniform_source_index,
        coordinates_angstrom: baseline.coordinates_angstrom,
        rotation: baseline.rotation,
        translation_angstrom: baseline.translation_angstrom,
        legacy_proposal_sha256,
        coordinate_sha256,
        source_receipt_sha256: hash.finish(),
    })
}

fn atomic_features(
    exact_source_receipt_sha256: [u8; 32],
) -> Result<Vec<RepositoryD0AtomicFeature>, RepositoryD0SourceError> {
    let mut definitions = Vec::<(Fixed64FeatureKind, bool, Vec<u64>)>::new();
    for donor in LIGAND_DONOR_ATOM_INDICES {
        push_donor_feature(&mut definitions, true, donor)?;
    }
    for acceptor in LIGAND_ACCEPTOR_ATOM_INDICES {
        definitions.push((
            Fixed64FeatureKind::LigandAcceptor,
            true,
            vec![acceptor as u64],
        ));
    }
    for donor in RECEPTOR_DONOR_ATOM_INDICES {
        push_donor_feature(&mut definitions, false, donor)?;
    }
    for acceptor in RECEPTOR_ACCEPTOR_ATOM_INDICES {
        definitions.push((
            Fixed64FeatureKind::ReceptorAcceptor,
            false,
            vec![acceptor as u64],
        ));
    }
    push_charge_features(&mut definitions, true, &LIGAND_PARTIAL_CHARGES)?;
    push_charge_features(&mut definitions, false, &RECEPTOR_PARTIAL_CHARGES)?;
    definitions.push((
        Fixed64FeatureKind::LigandShapeAxis,
        true,
        heavy_atom_indices(&LIGAND_ATOMIC_NUMBERS)?,
    ));
    definitions.push((
        Fixed64FeatureKind::PocketShapeAxis,
        false,
        heavy_atom_indices(&RECEPTOR_ATOMIC_NUMBERS)?,
    ));
    let mut features = definitions
        .iter()
        .map(|(kind, ligand, indices)| {
            let geometry =
                feature_geometry_sha256(*kind, *ligand, indices, exact_source_receipt_sha256);
            let mut allocation =
                CanonicalHash::new("betelgeuze.repository_d0_atomic_feature/native-v1");
            allocation.string(kind.id());
            allocation.digest(exact_source_receipt_sha256);
            allocation.digest(geometry);
            allocation.usize(indices.len());
            for &index in indices {
                allocation.u64(index);
            }
            RepositoryD0AtomicFeature {
                kind: *kind,
                atom_indices: indices.clone(),
                allocation_feature_receipt_sha256: allocation.finish(),
                feature_geometry_receipt_sha256: geometry,
            }
        })
        .collect::<Vec<_>>();
    features.sort_by_key(|feature| (feature.kind, feature.allocation_feature_receipt_sha256));
    if features.len() != 13 {
        return Err(RepositoryD0SourceError::InternalInvariant(
            "repository D0 atomic feature denominator changed",
        ));
    }
    Ok(features)
}

fn push_donor_feature(
    definitions: &mut Vec<(Fixed64FeatureKind, bool, Vec<u64>)>,
    ligand: bool,
    donor: usize,
) -> Result<(), RepositoryD0SourceError> {
    let (atomic_numbers, bonds, kind): (&[u8], &[(usize, usize)], Fixed64FeatureKind) = if ligand {
        (
            &LIGAND_ATOMIC_NUMBERS,
            &LIGAND_BONDS,
            Fixed64FeatureKind::LigandDonor,
        )
    } else {
        (
            &RECEPTOR_ATOMIC_NUMBERS,
            &RECEPTOR_BONDS,
            Fixed64FeatureKind::ReceptorDonor,
        )
    };
    let mut hydrogens = bonds
        .iter()
        .filter_map(|&(left, right)| match (left == donor, right == donor) {
            (true, false) => Some(right),
            (false, true) => Some(left),
            _ => None,
        })
        .filter(|&index| atomic_numbers.get(index) == Some(&1))
        .collect::<Vec<_>>();
    hydrogens.sort_unstable();
    hydrogens.dedup();
    let hydrogen = hydrogens
        .first()
        .copied()
        .ok_or(RepositoryD0SourceError::InternalInvariant(
            "repository D0 donor lacks its required attached hydrogen",
        ))?;
    definitions.push((kind, ligand, vec![donor as u64, hydrogen as u64]));
    Ok(())
}

fn push_charge_features(
    definitions: &mut Vec<(Fixed64FeatureKind, bool, Vec<u64>)>,
    ligand: bool,
    charges: &[f64],
) -> Result<(), RepositoryD0SourceError> {
    if charges.iter().any(|charge| !charge.is_finite()) {
        return Err(RepositoryD0SourceError::InternalInvariant(
            "repository D0 partial charge is non-finite",
        ));
    }
    let (positive, negative) = if ligand {
        (
            Fixed64FeatureKind::LigandPositiveSite,
            Fixed64FeatureKind::LigandNegativeSite,
        )
    } else {
        (
            Fixed64FeatureKind::ReceptorPositiveSite,
            Fixed64FeatureKind::ReceptorNegativeSite,
        )
    };
    for (index, charge) in charges.iter().copied().enumerate() {
        let kind = if charge >= PARTIAL_CHARGE_SITE_THRESHOLD {
            Some(positive)
        } else if charge <= -PARTIAL_CHARGE_SITE_THRESHOLD {
            Some(negative)
        } else {
            None
        };
        if let Some(kind) = kind {
            definitions.push((kind, ligand, vec![index as u64]));
        }
    }
    Ok(())
}

fn heavy_atom_indices(atomic_numbers: &[u8]) -> Result<Vec<u64>, RepositoryD0SourceError> {
    let indices = atomic_numbers
        .iter()
        .enumerate()
        .filter_map(|(index, atomic_number)| (*atomic_number != 1).then_some(index as u64))
        .collect::<Vec<_>>();
    if indices.len() < 2 {
        return Err(RepositoryD0SourceError::InternalInvariant(
            "repository D0 shape axis lacks two heavy atoms",
        ));
    }
    Ok(indices)
}

fn feature_geometry_sha256(
    kind: Fixed64FeatureKind,
    ligand: bool,
    indices: &[u64],
    exact_source_receipt_sha256: [u8; 32],
) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.repository_d0_feature_geometry/native-v1");
    hash.string(kind.id());
    hash.bool(ligand);
    hash.digest(exact_source_receipt_sha256);
    hash.usize(indices.len());
    for index in indices {
        hash.u64(*index);
        let point = if ligand {
            LIGAND_PREPARED_COORDINATES[*index as usize]
        } else {
            RECEPTOR_COORDINATES[*index as usize]
        };
        hash.vec3(point);
    }
    hash.bool(false);
    hash.finish()
}

fn feature_inventory_sha256(features: &[RepositoryD0AtomicFeature]) -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.repository_d0_feature_inventory/native-v1");
    hash.usize(features.len());
    for feature in features {
        hash.string(feature.kind.id());
        hash.digest(feature.allocation_feature_receipt_sha256);
        hash.digest(feature.feature_geometry_receipt_sha256);
    }
    hash.finish()
}

fn prepared_input_sha256() -> [u8; 32] {
    let mut hash = CanonicalHash::new("betelgeuze.repository_d0_prepared_input/native-v1");
    hash.digest(REQUEST_SHA256);
    hash.digest(LIGAND_SYSTEM_SHA256);
    hash.digest(RECEPTOR_SYSTEM_SHA256);
    hash.usize(LIGAND_PREPARED_COORDINATES.len());
    for coordinate in LIGAND_PREPARED_COORDINATES {
        hash.vec3(coordinate);
    }
    for ((atomic_number, charge), radius) in LIGAND_ATOMIC_NUMBERS
        .into_iter()
        .zip(LIGAND_PARTIAL_CHARGES)
        .zip(LIGAND_VDW_RADII)
    {
        hash.byte(atomic_number);
        hash.f64(charge);
        hash.f64(radius);
        hash.bool(atomic_number != 1);
    }
    hash.usize(LIGAND_BONDS.len());
    for (left, right) in LIGAND_BONDS {
        hash.usize(left);
        hash.usize(right);
    }
    hash.usize(RECEPTOR_COORDINATES.len());
    for coordinate in RECEPTOR_COORDINATES {
        hash.vec3(coordinate);
    }
    for ((atomic_number, charge), radius) in RECEPTOR_ATOMIC_NUMBERS
        .into_iter()
        .zip(RECEPTOR_PARTIAL_CHARGES)
        .zip(RECEPTOR_VDW_RADII)
    {
        hash.byte(atomic_number);
        hash.f64(charge);
        hash.f64(radius);
        hash.bool(atomic_number != 1);
    }
    hash.usize(RECEPTOR_BONDS.len());
    for (left, right) in RECEPTOR_BONDS {
        hash.usize(left);
        hash.usize(right);
    }
    hash.vec3(Vec3::default());
    hash.f64(REPOSITORY_D0_POCKET_RADIUS_ANGSTROM);
    hash.usize(REPOSITORY_D0_CANDIDATE_DENOMINATOR);
    hash.usize(REPOSITORY_D0_TOP_K);
    hash.u64(REPOSITORY_D0_SEED);
    hash.bool(false);
    hash.finish()
}

fn bundle_sha256(
    exact_source: &RepositoryD0ProposalSource,
    v7_control_sources: &[RepositoryD0ProposalSource; 24],
    retained_sources: &[RepositoryD0ProposalSource; 4],
    atomic_features: &[RepositoryD0AtomicFeature],
    prepared_input_receipt_sha256: [u8; 32],
    feature_geometry_inventory_sha256: [u8; 32],
    pocket_normal: Vec3,
) -> [u8; 32] {
    let mut hash = CanonicalHash::new(REPOSITORY_D0_SCHEMA_ID);
    hash.string(REPOSITORY_D0_PROFILE_ID);
    hash.digest(REQUEST_SHA256);
    hash.digest(AUTHORITY_INPUT_RECEIPT_SHA256);
    hash.digest(LIGAND_SYSTEM_SHA256);
    hash.digest(RECEPTOR_SYSTEM_SHA256);
    hash.digest(exact_source.source_receipt_sha256);
    hash.usize(v7_control_sources.len());
    for source in v7_control_sources {
        hash.u32(source.source_index);
        hash.u32(source.upstream_uniform_source_index);
        hash.digest(source.source_receipt_sha256);
    }
    hash.usize(retained_sources.len());
    for source in retained_sources {
        hash.u32(source.source_index);
        hash.digest(source.source_receipt_sha256);
    }
    hash.usize(atomic_features.len());
    for feature in atomic_features {
        hash.string(feature.kind.id());
        hash.digest(feature.allocation_feature_receipt_sha256);
        hash.digest(feature.feature_geometry_receipt_sha256);
    }
    hash.digest(prepared_input_receipt_sha256);
    hash.digest(feature_geometry_inventory_sha256);
    hash.vec3(pocket_normal);
    hash.usize(REPOSITORY_D0_CANDIDATE_DENOMINATOR);
    hash.bool(false);
    hash.finish()
}

fn pocket_normal() -> Result<Vec3, RepositoryD0SourceError> {
    let receptor_centroid = centroid(&RECEPTOR_COORDINATES);
    let direction = Vec3::default().minus(receptor_centroid);
    let norm = direction.norm();
    if !norm.is_finite() || norm <= 1.0e-12 {
        return Err(RepositoryD0SourceError::InternalInvariant(
            "repository D0 pocket normal is degenerate",
        ));
    }
    let value = direction.scale(1.0 / norm);
    if !value.is_finite() {
        return Err(RepositoryD0SourceError::InternalInvariant(
            "repository D0 pocket normal is non-finite",
        ));
    }
    Ok(value)
}

fn centroid<const N: usize>(points: &[Vec3; N]) -> Vec3 {
    points
        .iter()
        .copied()
        .fold(Vec3::default(), Vec3::plus)
        .scale(1.0 / N as f64)
}

fn rotate(rotation: [[f64; 3]; 3], point: Vec3) -> Vec3 {
    Vec3::new(
        rotation[0][0] * point.x + rotation[0][1] * point.y + rotation[0][2] * point.z,
        rotation[1][0] * point.x + rotation[1][1] * point.y + rotation[1][2] * point.z,
        rotation[2][0] * point.x + rotation[2][1] * point.y + rotation[2][2] * point.z,
    )
}

fn haar_rotation(proposal_index: usize) -> [[f64; 3]; 3] {
    if proposal_index == 0 {
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]];
    }
    let first = counter_uniform(proposal_index, "haar-rotation", 0);
    let second = counter_uniform(proposal_index, "haar-rotation", 1);
    let third = counter_uniform(proposal_index, "haar-rotation", 2);
    let root_one_minus = (1.0 - first).sqrt();
    let root_first = first.sqrt();
    let x = root_one_minus * (2.0 * core::f64::consts::PI * second).sin();
    let y = root_one_minus * (2.0 * core::f64::consts::PI * second).cos();
    let z = root_first * (2.0 * core::f64::consts::PI * third).sin();
    let w = root_first * (2.0 * core::f64::consts::PI * third).cos();
    [
        [
            1.0 - 2.0 * (y * y + z * z),
            2.0 * (x * y - z * w),
            2.0 * (x * z + y * w),
        ],
        [
            2.0 * (x * y + z * w),
            1.0 - 2.0 * (x * x + z * z),
            2.0 * (y * z - x * w),
        ],
        [
            2.0 * (x * z - y * w),
            2.0 * (y * z + x * w),
            1.0 - 2.0 * (x * x + y * y),
        ],
    ]
}

fn spherical_offset(proposal_index: usize) -> Vec3 {
    let azimuth_uniform = counter_uniform(proposal_index, "pocket-translation", 0);
    let z_uniform = counter_uniform(proposal_index, "pocket-translation", 1);
    let radial_uniform = counter_uniform(proposal_index, "pocket-translation", 2);
    let azimuth = 2.0 * core::f64::consts::PI * azimuth_uniform;
    let z_component = 2.0 * z_uniform - 1.0;
    let planar = (1.0 - z_component * z_component).max(0.0).sqrt();
    let radius = REPOSITORY_D0_TRANSLATION_RADIUS_ANGSTROM * radial_uniform.powf(1.0 / 3.0);
    Vec3::new(
        radius * planar * azimuth.cos(),
        radius * planar * azimuth.sin(),
        radius * z_component,
    )
}

fn counter_uniform(proposal_index: usize, domain: &str, counter: u64) -> f64 {
    let payload = format!(
        "{{\"counter\":{counter},\"domain\":\"{domain}\",\"prng_id\":\"sha256_counter_uniform_binary64/1.0.0\",\"proposal_index\":{proposal_index},\"seed\":{REPOSITORY_D0_SEED}}}"
    );
    let mut hash = crate::sha256::Sha256::new();
    hash.update(payload.as_bytes());
    let digest = hash.finalize();
    let integer = u64::from_be_bytes([
        digest[0], digest[1], digest[2], digest[3], digest[4], digest[5], digest[6], digest[7],
    ]);
    (integer as f64 + 0.5) / 18_446_744_073_709_551_616.0
}

const fn digest(value: &str) -> [u8; 32] {
    let bytes = value.as_bytes();
    assert!(bytes.len() == 64);
    let mut result = [0_u8; 32];
    let mut index = 0;
    while index < 32 {
        result[index] = (nibble(bytes[index * 2]) << 4) | nibble(bytes[index * 2 + 1]);
        index += 1;
    }
    result
}

const fn nibble(value: u8) -> u8 {
    match value {
        b'0'..=b'9' => value - b'0',
        b'a'..=b'f' => value - b'a' + 10,
        _ => panic!("repository D0 digest is not lowercase hexadecimal"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{Fixed64Allocation, Fixed64Lane};

    #[test]
    fn exact_d0_materializer_preserves_fixed64_denominator_and_missing_features() {
        let bundle = materialize_repository_synthetic_d0_sources().unwrap();
        let allocation = Fixed64Allocation::build(bundle.feature_inventory().unwrap()).unwrap();

        assert_eq!(bundle.v7_control_sources().len(), 24);
        assert_eq!(bundle.retained_sources().len(), 4);
        assert_eq!(bundle.atomic_features().len(), 13);
        assert_eq!(allocation.slots().len(), 64);
        assert_eq!(allocation.ready_count(), 54);
        assert_eq!(allocation.typed_failure_count(), 10);
        assert_eq!(
            allocation
                .slots()
                .iter()
                .filter(|slot| slot.lane() == Fixed64Lane::TrueConformerIndependentSo3)
                .filter(|slot| !slot.generation_eligible())
                .count(),
            8
        );
        assert_eq!(
            allocation
                .slots()
                .iter()
                .filter(|slot| slot.lane() == Fixed64Lane::AromaticPlane)
                .filter(|slot| !slot.generation_eligible())
                .count(),
            2
        );
        assert!(!allocation.result_dependent_allocation());
        assert!(!allocation.molecular_execution_authorized());
    }

    #[test]
    fn guided_controls_rebind_the_predeclared_uniform_indices_without_duplication() {
        let bundle = materialize_repository_synthetic_d0_sources().unwrap();
        let controls = bundle.v7_control_sources();

        assert_eq!(
            std::array::from_fn::<_, 24, _>(|index| controls[index].source_index()),
            std::array::from_fn(|index| index as u32)
        );
        assert_eq!(
            controls[8..]
                .iter()
                .map(RepositoryD0ProposalSource::upstream_uniform_source_index)
                .collect::<Vec<_>>(),
            REPOSITORY_D0_GUIDED_SOURCE_INDICES
        );
        assert_eq!(
            controls[..8]
                .iter()
                .map(RepositoryD0ProposalSource::upstream_uniform_source_index)
                .collect::<Vec<_>>(),
            (0_u32..8).collect::<Vec<_>>()
        );
        let unique = controls[8..]
            .iter()
            .map(RepositoryD0ProposalSource::coordinate_sha256)
            .collect::<std::collections::BTreeSet<_>>();
        assert_eq!(unique.len(), 16);
    }

    #[test]
    fn source_and_feature_receipts_are_reproducible_and_nonzero() {
        let first = materialize_repository_synthetic_d0_sources().unwrap();
        let second = materialize_repository_synthetic_d0_sources().unwrap();

        assert_eq!(first, second);
        assert_eq!(first.receipt_sha256(), REPOSITORY_D0_EXPECTED_BUNDLE_SHA256);
        assert_eq!(
            first.feature_geometry_inventory_sha256(),
            REPOSITORY_D0_EXPECTED_FEATURE_INVENTORY_SHA256
        );
        assert_eq!(
            first.prepared_input_receipt_sha256(),
            REPOSITORY_D0_EXPECTED_PREPARED_INPUT_SHA256
        );
        assert_eq!(
            Fixed64Allocation::build(first.feature_inventory().unwrap())
                .unwrap()
                .receipt_sha256(),
            REPOSITORY_D0_EXPECTED_ALLOCATION_SHA256
        );
        assert!(first
            .v7_control_sources()
            .iter()
            .all(|source| source.source_receipt_sha256() != [0; 32]));
        assert!(first.atomic_features().iter().all(|feature| {
            feature.allocation_feature_receipt_sha256() != [0; 32]
                && feature.feature_geometry_receipt_sha256() != [0; 32]
        }));
        let normal = first.pocket_normal();
        assert!((normal.norm() - 1.0).abs() < 2.0e-15);
        assert!(normal.x < 0.0 && normal.y < 0.0 && normal.z == 0.0);
    }

    #[test]
    fn exact_prepared_geometry_is_exposed_without_authority_or_mutation() {
        let bundle = materialize_repository_synthetic_d0_sources().unwrap();

        assert_eq!(
            bundle.ligand_prepared_coordinates_angstrom(),
            &LIGAND_PREPARED_COORDINATES
        );
        assert_eq!(
            bundle.receptor_coordinates_angstrom(),
            &RECEPTOR_COORDINATES
        );
        assert_eq!(bundle.ligand_vdw_radii_angstrom(), &LIGAND_VDW_RADII);
        assert_eq!(bundle.receptor_vdw_radii_angstrom(), &RECEPTOR_VDW_RADII);
        assert_eq!(
            bundle.ligand_heavy_atom_mask(),
            [true, true, false, true, false]
        );
        assert_eq!(bundle.ligand_atomic_numbers(), &LIGAND_ATOMIC_NUMBERS);
        assert_eq!(bundle.receptor_atomic_numbers(), &RECEPTOR_ATOMIC_NUMBERS);
        assert_eq!(
            bundle.ligand_partial_charges_elementary(),
            &LIGAND_PARTIAL_CHARGES
        );
        assert_eq!(
            bundle.receptor_partial_charges_elementary(),
            &RECEPTOR_PARTIAL_CHARGES
        );
        assert_eq!(bundle.ligand_bonds(), &LIGAND_BONDS);
        assert_eq!(bundle.receptor_bonds(), &RECEPTOR_BONDS);
        assert_eq!(bundle.pocket_center_angstrom(), Vec3::default());
        assert_eq!(bundle.pocket_radius_angstrom(), 10.0);
    }

    #[test]
    fn atomic_features_are_derived_from_frozen_bonds_charges_and_heavy_atoms() {
        let bundle = materialize_repository_synthetic_d0_sources().unwrap();
        let observed = bundle
            .atomic_features()
            .iter()
            .map(|feature| (feature.kind(), feature.atom_indices().to_vec()))
            .collect::<std::collections::BTreeSet<_>>();
        let expected = [
            (Fixed64FeatureKind::LigandDonor, vec![1, 2]),
            (Fixed64FeatureKind::LigandDonor, vec![3, 4]),
            (Fixed64FeatureKind::LigandAcceptor, vec![1]),
            (Fixed64FeatureKind::LigandAcceptor, vec![3]),
            (Fixed64FeatureKind::ReceptorDonor, vec![1, 2]),
            (Fixed64FeatureKind::ReceptorAcceptor, vec![0]),
            (Fixed64FeatureKind::ReceptorAcceptor, vec![1]),
            (Fixed64FeatureKind::LigandPositiveSite, vec![4]),
            (Fixed64FeatureKind::LigandNegativeSite, vec![3]),
            (Fixed64FeatureKind::ReceptorPositiveSite, vec![4]),
            (Fixed64FeatureKind::ReceptorNegativeSite, vec![0]),
            (Fixed64FeatureKind::LigandShapeAxis, vec![0, 1, 3]),
            (Fixed64FeatureKind::PocketShapeAxis, vec![0, 1, 3]),
        ]
        .into_iter()
        .collect::<std::collections::BTreeSet<_>>();

        assert_eq!(observed, expected);
        assert!(observed.iter().all(|(kind, _)| {
            !matches!(
                kind,
                Fixed64FeatureKind::LigandAromaticPlane | Fixed64FeatureKind::ReceptorAromaticPlane
            )
        }));
    }

    #[test]
    fn native_coordinates_match_the_frozen_current_v7_source_receipts_bitwise() {
        let bundle = materialize_repository_synthetic_d0_sources().unwrap();

        assert_eq!(
            std::array::from_fn::<_, 24, _>(|index| {
                bundle.v7_control_sources()[index].coordinate_sha256()
            }),
            V7_LEGACY_NATIVE_COORDINATE_SHA256
        );
        assert_eq!(
            std::array::from_fn::<_, 4, _>(|index| {
                bundle.retained_sources()[index].coordinate_sha256()
            }),
            RETAINED_LEGACY_NATIVE_COORDINATE_SHA256
        );
    }

    #[test]
    fn baseline_geometry_is_pocket_centered_or_within_the_frozen_radius() {
        let bundle = materialize_repository_synthetic_d0_sources().unwrap();
        for source in bundle.v7_control_sources() {
            let center = centroid(source.coordinates_angstrom());
            let expected = if source.upstream_uniform_source_index() < 8 {
                0.0
            } else {
                center.norm()
            };
            if source.source_index() < 8 {
                assert!(center.norm() < 2.0e-15);
            } else {
                assert!(
                    expected > 0.0
                        && expected <= REPOSITORY_D0_TRANSLATION_RADIUS_ANGSTROM + 1.0e-12
                );
            }
        }
    }
}
