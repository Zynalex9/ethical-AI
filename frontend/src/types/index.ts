// TypeScript type definitions for the application

// User types
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
export interface Template {
    id: string;
    template_id: string;
    name: string;
    description: string | null;
    domain: 'finance' | 'healthcare' | 'criminal_justice' | 'education' | 'employment' | 'general';
    rules: Record<string, unknown>;
    version: number;
    is_active: boolean;
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
