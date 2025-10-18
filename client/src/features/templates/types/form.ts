import type { Protocol } from "../duck/dto"

export interface CreateTemplateForm {
    name: string,
    protocol: Protocol
    default_port: string
    requires_tls: boolean
}

export interface EditTemplateForm {
    name: string,
    protocol: Protocol
    default_port: string
    requires_tls: boolean
    is_active: boolean
}
