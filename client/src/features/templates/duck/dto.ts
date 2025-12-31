export type Protocol = 'vless' | 'vmess' | 'trojan' | 'shadowsocks';

export interface TemplateDTO {
  base_settings: Record<string, unknown>; // TODO define unknown
  created_at: string;
  default_port: number;
  description: string;
  id: string;
  is_active: boolean;
  name: string;
  protocol: Protocol;
  requires_domain: boolean;
  requires_tls: boolean;
  stream_settings: Record<string, unknown>; // TOD define unknown
  updated_at: string;
  variables: unknown[]; // TOD define unknown
}

export interface CreateTemplateDTO {
  name: string;
  protocol: Protocol;
  default_port: number;
  requires_tls: boolean;
  config_template: '';
}

export interface EditTemplateDTO {
    name: string,
    protocol: Protocol
    default_port: number
    requires_tls: boolean
    is_active: boolean
}