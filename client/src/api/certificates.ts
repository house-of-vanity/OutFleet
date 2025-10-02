import { api } from './api';

export interface Certificate {}

export const getCertificates = api.get<never, Certificate[]>('/certificates');
