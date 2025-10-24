use thiserror::Error;

#[derive(Error, Debug)]
pub enum AcmeError {
    #[error("ACME account creation failed: {0}")]
    AccountCreation(String),

    #[error("ACME order creation failed: {0}")]
    OrderCreation(String),

    #[error("ACME challenge failed: {0}")]
    Challenge(String),

    #[error("DNS propagation timeout")]
    DnsPropagationTimeout,

    #[error("Certificate generation failed: {0}")]
    CertificateGeneration(String),

    #[error("Cloudflare API error: {0}")]
    CloudflareApi(String),

    #[error("DNS provider not found")]
    DnsProviderNotFound,

    #[error("Invalid domain: {0}")]
    InvalidDomain(String),

    #[error("HTTP request failed: {0}")]
    HttpRequest(#[from] reqwest::Error),

    #[error("JSON parsing failed: {0}")]
    JsonParsing(#[from] serde_json::Error),

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("Instant ACME error: {0}")]
    InstantAcme(String),
}
