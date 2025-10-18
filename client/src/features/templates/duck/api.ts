import type { AxiosResponse } from 'axios';
import { api } from '../../../api/api';
import type { TemplateDTO, CreateTemplateDTO, EditTemplateDTO } from './dto';

export const getTemplates = () =>
  api.get<never, AxiosResponse<TemplateDTO[]>>('/templates');

export const createTemplate = (params: CreateTemplateDTO) =>
  api.post<AxiosResponse>('templates', params, {
    headers: {
      'Content-Type': 'application/json',
    },
  });

export const getTemplateById = (id: string) =>
  api.get<string, AxiosResponse<TemplateDTO>>(`/templates/${id}`);

export const patchTemplate = (id: string, template: EditTemplateDTO) =>
  api.put(`/templates/${id}`, template, {
    headers: { 'Content-Type': 'application/json' },
  });

export const deleteTemplate = (id: string) => api.delete(`/templates/${id}`);
