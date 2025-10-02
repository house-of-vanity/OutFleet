import { api } from './api';

export interface Server {}

export const getServers = api.get<never, Server[]>('/servers');
