/**
 * Interfaces matching the backend schemas
 * Example based on a typical Resource entity
 */

export interface Resource {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
}

export interface CreateResourceInput {
  name: string;
  description?: string;
}

export interface UpdateResourceInput {
  name?: string;
  description?: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ApiError {
  detail: string;
  status: number;
}