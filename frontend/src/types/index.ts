export interface User {
    id: string;
    email: string;
    name: string;
    role: 'user' | 'admin' | 'auditor';
    is_active: boolean;
    created_at: string;
    last_login: string | null;
}

// Project types
export interface Project {
    id: string;
    name: string;
    description: string | null;
    owner_id: string;
    created_at: string;
    updated_at: string;
    model_count?: number;
    dataset_count?: number;
    requirement_count?: number;
}

// Model types
export interface MLModel {
    id: string;
    project_id: string;
    name: string;
    description: string | null;
    file_path: string;
    file_size: number;
    model_type: 'sklearn' | 'tensorflow' | 'pytorch' | 'onnx' | 'xgboost' | 'lightgbm' | 'unknown';
    model_metadata: Record<string, unknown>;
    version: string;
    uploaded_at: string;
    uploaded_by_id: string | null;
}

// Dataset types
export interface Dataset {
    id: string;
    project_id: string;
    name: string;
    description: string | null;
    file_path: string;
    row_count: number;
    column_count: number;
    columns: string[];
    sensitive_attributes: string[];
    target_column: string | null;
    profile_data: Record<string, unknown>;
    uploaded_at: string;
}

// Template types
export interface TemplateRuleItem {
    metric: string;
    operator: string;
    value: number;
    principle?: string;
    description?: string;
}

export interface TemplateRules {
    principles: string[];
    reference: string;
    items: TemplateRuleItem[];
}

export interface Template {
    id: string;
    template_id: string;
    name: string;
    description: string | null;
    domain: 'finance' | 'healthcare' | 'criminal_justice' | 'education' | 'employment' | 'general';
    rules: TemplateRules;
    version: number;
    is_active: boolean;
    created_at: string;
    updated_at: string;
}

// Requirement types
export interface Requirement {
    id: string;
    project_id: string;
    name: string;
    description: string | null;
    principle: 'fairness' | 'transparency' | 'privacy' | 'accountability';
    specification: Record<string, unknown>;
    based_on_template_id: string | null;
    status: 'draft' | 'active' | 'archived';
    version: number;
    created_at: string;
}

// Validation types
export interface Validation {
    id: string;
    requirement_id: string;
    model_id: string;
    dataset_id: string;
    status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
    progress: number;
    started_at: string | null;
    completed_at: string | null;
    mlflow_run_id: string | null;
    error_message: string | null;
}

export interface ValidationResult {
    id: string;
    validation_id: string;
    principle: string;
    metric_name: string;
    metric_value: number | null;
    threshold: number | null;
    passed: boolean;
    details: Record<string, unknown>;
}

// Validation Suite types (NEW)
export interface ValidationSuite {
    id: string;
    model_id: string;
    dataset_id: string;
    celery_task_id: string | null;
    status: 'pending' | 'running' | 'completed' | 'failed';
    overall_passed: boolean | null;
    fairness_validation_id: string | null;
    transparency_validation_id: string | null;
    privacy_validation_id: string | null;
    started_at: string | null;
    completed_at: string | null;
    error_message: string | null;
    created_by_id: string;
    created_at: string;
}

export interface ValidationSuiteResponse {
    suite_id: string;
    task_id: string;
    status: string;
    message: string;
}

export interface TaskStatus {
    task_id: string;
    state: 'PENDING' | 'PROGRESS' | 'SUCCESS' | 'FAILURE';
    progress: number;
    current_step: string | null;
    result: any | null;
    error: string | null;
}

export interface SuiteResults {
    suite_id: string;
    status: string;
    overall_passed: boolean | null;
    started_at: string | null;
    completed_at: string | null;
    error_message: string | null;
    validations: {
        fairness?: {
            validation_id: string;
            status: string;
            progress: number;
            mlflow_run_id: string | null;
            completed_at: string | null;
        };
        transparency?: {
            validation_id: string;
            status: string;
            progress: number;
            mlflow_run_id: string | null;
            completed_at: string | null;
        };
        privacy?: {
            validation_id: string;
            status: string;
            progress: number;
            mlflow_run_id: string | null;
            completed_at: string | null;
        };
    };
}

// Fairness report types
export interface FairnessMetric {
    metric_name: string;
    overall_value: number;
    by_group: Record<string, number | Record<string, number>>;
    threshold: number;
    passed: boolean;
    description: string;
}

export interface FairnessReport {
    sensitive_feature: string;
    groups: string[];
    sample_sizes: Record<string, number>;
    metrics: FairnessMetric[];
    overall_passed: boolean;
    visualizations?: Record<string, string>;
}

// Auth types
export interface LoginCredentials {
    email: string;
    password: string;
}

export interface RegisterData {
    email: string;
    password: string;
    name: string;
}

export interface AuthTokens {
    access_token: string;
    refresh_token: string;
    token_type: string;
}

// Notification types (Phase 3)
export interface Notification {
    id: string;
    user_id: string;
    project_id: string | null;
    validation_suite_id: string | null;
    message: string;
    severity: 'info' | 'warning' | 'error' | 'success';
    read: boolean;
    link: string | null;
    details: Record<string, unknown> | null;
    created_at: string;
}

// Scheduled Validation types (Phase 3)
export interface ScheduledValidation {
    id: string;
    project_id: string;
    enabled: boolean;
    frequency: 'daily' | 'weekly' | 'monthly';
    last_run_at: string | null;
    next_run_at: string | null;
    created_at: string;
    updated_at: string;
}

// Differential Privacy result (Phase 3)
export interface DPResult {
    measured_epsilon: number;
    target_epsilon: number;
    budget_satisfied: boolean;
    sensitivities: Record<string, number>;
    noise_applied: boolean;
    noised_epsilon: number | null;
    details: string[];
}

// HIPAA check result (Phase 3)
export interface HIPAACheckResult {
    identifier: string;
    passed: boolean;
    columns_flagged: string[];
    detail: string;
}

export interface HIPAAReport {
    overall_passed: boolean;
    total_checks: number;
    passed_checks: number;
    failed_checks: number;
    results: HIPAACheckResult[];
}

// Remediation types (Phase 3)
export interface RemediationStep {
    id: string;
    description: string;
    done: boolean;
    doc_link: string | null;
}

export interface RemediationChecklist {
    id: string;
    validation_suite_id: string;
    principle: string;
    steps: RemediationStep[];
    all_done: boolean;
}
