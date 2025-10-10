import type { AxiosResponse } from 'axios';
import { api } from '../../../api/api';
import type { TemplateDTO } from './dto';

export const getTemplates = () => api.get<never, AxiosResponse<TemplateDTO[]>>('/templates');