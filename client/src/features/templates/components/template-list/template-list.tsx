import type { FC } from 'react';
import type { TemplateDTO } from '../../duck';
import { TemplateView } from './template-view';

export interface TemplateListProps {
  templates: TemplateDTO[];
}

export const TemplateList: FC<TemplateListProps> = ({ templates }) => {
  return (
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Protocol</th>
          <th>Port</th>
          <th>TLS</th>
          <th>Active</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {templates.map((template) => (
          <TemplateView template={template} key={template.id}/>
        ))}
      </tbody>
    </table>
  );
};
