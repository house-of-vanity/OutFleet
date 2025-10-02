import { api } from './api';

export interface Template {}

export const getTemplates = api.get<never, Template[]>('/templates');
