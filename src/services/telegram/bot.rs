use teloxide::{Bot, prelude::*};
use tokio::sync::oneshot;

use crate::database::DatabaseManager;
use super::handlers::{self, Command};

/// Run the bot polling loop
pub async fn run_polling(
    bot: Bot,
    db: DatabaseManager,
    mut shutdown_rx: oneshot::Receiver<()>,
) {
    tracing::info!("Starting Telegram bot polling...");

    let handler = dptree::entry()
        .branch(
            Update::filter_message()
                .branch(
                    dptree::entry()
                        .filter_command::<Command>()
                        .endpoint(handlers::handle_command)
                )
                .branch(
                    dptree::endpoint(handlers::handle_message)
                )
        )
        .branch(
            Update::filter_callback_query()
                .endpoint(handlers::handle_callback_query)
        );

    let mut dispatcher = Dispatcher::builder(bot.clone(), handler)
        .dependencies(dptree::deps![db])
        .enable_ctrlc_handler()
        .build();

    // Run dispatcher with shutdown signal
    tokio::select! {
        _ = dispatcher.dispatch() => {
            tracing::info!("Telegram bot polling stopped");
        }
        _ = shutdown_rx => {
            tracing::info!("Telegram bot received shutdown signal");
        }
    }
}