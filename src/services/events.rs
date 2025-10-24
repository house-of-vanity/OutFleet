use std::sync::OnceLock;
use tokio::sync::broadcast;
use uuid::Uuid;

#[derive(Clone, Debug)]
pub enum SyncEvent {
    InboundChanged(Uuid),    // server_id
    UserAccessChanged(Uuid), // server_id
}

static EVENT_SENDER: OnceLock<broadcast::Sender<SyncEvent>> = OnceLock::new();

/// Initialize the event bus and return a receiver
pub fn init_event_bus() -> broadcast::Receiver<SyncEvent> {
    let (tx, rx) = broadcast::channel(100);
    EVENT_SENDER.set(tx).expect("Event bus already initialized");
    rx
}

/// Send a sync event (non-blocking)
pub fn send_sync_event(event: SyncEvent) {
    if let Some(sender) = EVENT_SENDER.get() {
        match sender.send(event.clone()) {
            Ok(_) => tracing::info!("Event sent: {:?}", event),
            Err(_) => tracing::warn!("No event receivers"),
        }
    } else {
        tracing::error!("Event bus not initialized");
    }
}
