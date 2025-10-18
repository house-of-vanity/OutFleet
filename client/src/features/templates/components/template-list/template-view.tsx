import type { FC } from 'react';
import { deleteTemplateAction, type TemplateDTO } from '../../duck';
import { useDisclosure } from '@heroui/react';
import { TemplateEdit } from './template-edit';
import { useAppDispatch } from '../../../../common/hooks';

export interface TemplateViewProps {
  template: TemplateDTO;
}

export const TemplateView: FC<TemplateViewProps> = ({ template }) => {
  const dispatch = useAppDispatch();
  const { isOpen, onOpen, onOpenChange } = useDisclosure();

  const handleDeleteTemplate = () => {
    if (confirm('Delete template?')) {
      dispatch(deleteTemplateAction(template.id));
    }
  };

  return (
    <>
      <tr>
        <td>{template.name}</td>
        <td>{template.protocol}</td>
        <td>{template.default_port}</td>
        <td>{template.requires_tls ? 'Yes' : 'No'}</td>
        <td>{template.is_active ? 'Yes' : 'No'}</td>
        <td>
          <button className="btn btn-primary" onClick={onOpen}>
            Edit
          </button>
          <button
            className="btn btn-danger"
            onClick={handleDeleteTemplate}
          >
            Delete
          </button>
        </td>
      </tr>
      <TemplateEdit
        templateId={template.id}
        onOpenChange={onOpenChange}
        isOpen={isOpen}
      />
    </>
  );
};
