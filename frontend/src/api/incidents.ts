/**
 * Ground-truth incidents and affected trace lookups API client.
 */

import { buildQueryString, request } from './client';
import { Incident, IncidentTrace } from '../types/incident';

export const incidentsApi = {
  /** List historical ground-truth incidents */
  listIncidents: (params?: {
    scenario_type?: string;
    severity?: string;
    start_time?: string;
    end_time?: string;
  }) =>
    request<Incident[]>(
      `/api/v1/incidents${buildQueryString(params || {})}`
    ),

  /** Get details of a single incident */
  getIncident: (id: string) =>
    request<Incident>(`/api/v1/incidents/${encodeURIComponent(id)}`),

  /** List executions affected by an incident */
  getIncidentTraces: (id: string) =>
    request<IncidentTrace[]>(
      `/api/v1/incidents/${encodeURIComponent(id)}/traces`
    ),
};
