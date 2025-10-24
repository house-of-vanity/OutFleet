use std::fmt;

#[derive(Debug)]
pub enum UriGeneratorError {
    UnsupportedProtocol(String),
    MissingRequiredField(String),
    InvalidConfiguration(String),
    VariableSubstitution(String),
    JsonParsing(String),
    UriEncoding(String),
}

impl fmt::Display for UriGeneratorError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            UriGeneratorError::UnsupportedProtocol(protocol) => {
                write!(f, "Unsupported protocol: {}", protocol)
            }
            UriGeneratorError::MissingRequiredField(field) => {
                write!(f, "Missing required field: {}", field)
            }
            UriGeneratorError::InvalidConfiguration(msg) => {
                write!(f, "Invalid configuration: {}", msg)
            }
            UriGeneratorError::VariableSubstitution(msg) => {
                write!(f, "Variable substitution error: {}", msg)
            }
            UriGeneratorError::JsonParsing(msg) => {
                write!(f, "JSON parsing error: {}", msg)
            }
            UriGeneratorError::UriEncoding(msg) => {
                write!(f, "URI encoding error: {}", msg)
            }
        }
    }
}

impl std::error::Error for UriGeneratorError {}

impl From<serde_json::Error> for UriGeneratorError {
    fn from(err: serde_json::Error) -> Self {
        UriGeneratorError::JsonParsing(err.to_string())
    }
}

// Note: urlencoding crate doesn't have EncodingError in current version
// impl From<urlencoding::EncodingError> for UriGeneratorError {
//     fn from(err: urlencoding::EncodingError) -> Self {
//         UriGeneratorError::UriEncoding(err.to_string())
//     }
// }
