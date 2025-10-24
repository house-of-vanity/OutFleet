use axum::{extract::State, http::StatusCode, response::Json};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use crate::web::AppState;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskStatusResponse {
    pub name: String,
    pub description: String,
    pub schedule: String,
    pub status: String,
    pub last_run: Option<String>,
    pub next_run: Option<String>,
    pub total_runs: u64,
    pub success_count: u64,
    pub error_count: u64,
    pub last_error: Option<String>,
    pub last_duration_ms: Option<u64>,
}

#[derive(Debug, Serialize)]
pub struct TasksStatusResponse {
    pub tasks: HashMap<String, TaskStatusResponse>,
    pub summary: TasksSummary,
}

#[derive(Debug, Serialize)]
pub struct TasksSummary {
    pub total_tasks: usize,
    pub running_tasks: usize,
    pub successful_tasks: usize,
    pub failed_tasks: usize,
    pub idle_tasks: usize,
}

/// Get status of all scheduled tasks
pub async fn get_tasks_status(
    State(_state): State<AppState>,
) -> Result<Json<TasksStatusResponse>, StatusCode> {
    // Get task status from the scheduler
    // For now, we'll return a mock response since we need to expose the scheduler
    // In a real implementation, you'd store a reference to the TaskScheduler in AppState

    let mut tasks = HashMap::new();
    let mut running_count = 0;
    let mut success_count = 0;
    let mut error_count = 0;
    let mut idle_count = 0;

    // Mock data for demonstration - in real implementation, get from TaskScheduler
    let xray_sync_task = TaskStatusResponse {
        name: "Xray Synchronization".to_string(),
        description: "Synchronizes database state with xray servers".to_string(),
        schedule: "0 */5 * * * * (every 5 minutes)".to_string(),
        status: "Success".to_string(),
        last_run: Some(
            chrono::Utc::now()
                .format("%Y-%m-%d %H:%M:%S UTC")
                .to_string(),
        ),
        next_run: Some(
            (chrono::Utc::now() + chrono::Duration::minutes(5))
                .format("%Y-%m-%d %H:%M:%S UTC")
                .to_string(),
        ),
        total_runs: 120,
        success_count: 118,
        error_count: 2,
        last_error: None,
        last_duration_ms: Some(1234),
    };

    let cert_renewal_task = TaskStatusResponse {
        name: "Certificate Renewal".to_string(),
        description: "Renews Let's Encrypt certificates that expire within 15 days".to_string(),
        schedule: "0 0 2 * * * (daily at 2 AM)".to_string(),
        status: "Idle".to_string(),
        last_run: Some(
            (chrono::Utc::now() - chrono::Duration::hours(8))
                .format("%Y-%m-%d %H:%M:%S UTC")
                .to_string(),
        ),
        next_run: Some(
            (chrono::Utc::now() + chrono::Duration::hours(16))
                .format("%Y-%m-%d %H:%M:%S UTC")
                .to_string(),
        ),
        total_runs: 5,
        success_count: 5,
        error_count: 0,
        last_error: None,
        last_duration_ms: Some(567),
    };

    // Count task statuses
    match xray_sync_task.status.as_str() {
        "Running" => running_count += 1,
        "Success" => success_count += 1,
        "Error" => error_count += 1,
        "Idle" => idle_count += 1,
        _ => idle_count += 1,
    }

    match cert_renewal_task.status.as_str() {
        "Running" => running_count += 1,
        "Success" => success_count += 1,
        "Error" => error_count += 1,
        "Idle" => idle_count += 1,
        _ => idle_count += 1,
    }

    tasks.insert("xray_sync".to_string(), xray_sync_task);
    tasks.insert("cert_renewal".to_string(), cert_renewal_task);

    let summary = TasksSummary {
        total_tasks: tasks.len(),
        running_tasks: running_count,
        successful_tasks: success_count,
        failed_tasks: error_count,
        idle_tasks: idle_count,
    };

    let response = TasksStatusResponse { tasks, summary };

    Ok(Json(response))
}

/// Trigger manual execution of a specific task
pub async fn trigger_task(
    State(_state): State<AppState>,
    axum::extract::Path(task_id): axum::extract::Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    // In a real implementation, you'd trigger the actual task
    // For now, return a success response
    match task_id.as_str() {
        "xray_sync" | "cert_renewal" => Ok(Json(serde_json::json!({
            "success": true,
            "message": format!("Task '{}' has been triggered", task_id)
        }))),
        _ => Err(StatusCode::NOT_FOUND),
    }
}
