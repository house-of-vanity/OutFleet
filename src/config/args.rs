use clap::Parser;
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[command(name = "xray-admin")]
#[command(about = "A web admin panel for managing xray-core VPN proxy servers")]
#[command(version)]
pub struct Args {
    /// Configuration file path
    #[arg(short, long, value_name = "FILE")]
    pub config: Option<PathBuf>,

    /// Database connection URL
    #[arg(long, env = "DATABASE_URL")]
    pub database_url: Option<String>,

    /// Web server host address
    #[arg(long, default_value = "127.0.0.1")]
    pub host: Option<String>,

    /// Web server port
    #[arg(short, long)]
    pub port: Option<u16>,

    /// Log level (trace, debug, info, warn, error)
    #[arg(long, default_value = "info")]
    pub log_level: Option<String>,

    /// Base URL for the application (used in subscription links and Telegram messages)
    #[arg(long, env = "BASE_URL")]
    pub base_url: Option<String>,

    /// Validate configuration and exit
    #[arg(long)]
    pub validate_config: bool,

    /// Print default configuration and exit
    #[arg(long)]
    pub print_default_config: bool,
}

pub fn parse_args() -> Args {
    Args::parse()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_args_parsing() {
        let args = Args::try_parse_from(&[
            "xray-admin",
            "--config", "test.toml",
            "--port", "9090",
            "--log-level", "debug"
        ]).unwrap();

        assert_eq!(args.config, Some(PathBuf::from("test.toml")));
        assert_eq!(args.port, Some(9090));
        assert_eq!(args.log_level, Some("debug".to_string()));
    }
}