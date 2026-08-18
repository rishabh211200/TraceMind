/**
 * Simulator control, scenario catalog, and live chaos injection API client.
 */

import { request } from './client';
import {
  ChaosInjectionRequest,
  ChaosInjectionResponse,
  ChaosScenarioInfo,
  SimulationGenerateRequest,
  SimulationGenerateResponse,
} from '../types/simulator';

export const simulatorApi = {
  /** Get catalog of 7 supported causal chaos incident scenarios */
  listScenarios: () => request<ChaosScenarioInfo[]>('/api/v1/simulator/scenarios'),

  /** Trigger synthetic trace simulation run */
  generateSimulation: (payload: SimulationGenerateRequest) =>
    request<SimulationGenerateResponse>('/api/v1/simulator/generate', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** Inject targeted causal chaos experiment */
  injectChaos: (payload: ChaosInjectionRequest) =>
    request<ChaosInjectionResponse>('/api/v1/simulator/inject-chaos', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};
