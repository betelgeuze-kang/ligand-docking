use core::fmt;

/// Stable categories that callers can handle without parsing diagnostics.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum SearchErrorCode {
    EmptyLigand,
    EmptySurface,
    MissingLigandAnchor,
    TooManyItems,
    InvalidConfiguration,
    NonFiniteInput,
    InvalidRadius,
    InvalidAtomParameter,
    InvalidDirection,
    AtomIndexOutOfRange,
    DuplicateIdentifier,
    NoCompatibleAnchors,
    AllocationOverflow,
    CompositeWorkLimit,
    Evaluator,
    NonFiniteEvaluation,
    InternalInvariant,
}

/// A validation, allocation, evaluator, or search failure.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SearchError {
    code: SearchErrorCode,
    detail: String,
}

impl SearchError {
    #[must_use]
    pub fn new(code: SearchErrorCode, detail: impl Into<String>) -> Self {
        Self {
            code,
            detail: detail.into(),
        }
    }

    #[must_use]
    pub const fn code(&self) -> SearchErrorCode {
        self.code
    }

    #[must_use]
    pub fn detail(&self) -> &str {
        &self.detail
    }
}

impl fmt::Display for SearchError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{:?}: {}", self.code, self.detail)
    }
}

impl std::error::Error for SearchError {}

/// Error returned by a user-supplied native energy/force evaluator.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EvaluationError {
    detail: String,
}

impl EvaluationError {
    #[must_use]
    pub fn new(detail: impl Into<String>) -> Self {
        Self {
            detail: detail.into(),
        }
    }

    #[must_use]
    pub fn detail(&self) -> &str {
        &self.detail
    }
}

impl fmt::Display for EvaluationError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(&self.detail)
    }
}

impl std::error::Error for EvaluationError {}
