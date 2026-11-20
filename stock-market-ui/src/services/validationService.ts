import apiClient from "../api/client";

import type {
  ActiveValidationRun,
  ValidationProgress,
} from "../types/validation";

export async function getActiveValidationRun(): Promise<ActiveValidationRun> {
  const response = await apiClient.get<ActiveValidationRun>(
    "/analysis/validation-runs/active"
  );

  return response.data;
}

export async function getValidationProgress(
  validationRunId: number
): Promise<ValidationProgress> {
  const response = await apiClient.get<ValidationProgress>(
    `/analysis/validation-runs/${validationRunId}/progress`
  );

  return response.data;
}