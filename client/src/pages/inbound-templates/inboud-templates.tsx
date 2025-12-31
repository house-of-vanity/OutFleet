import type { RouteObject } from 'react-router';
import { AddTemplate, fetchTemplates, getTemplatesState, TemplateList } from '../../features/templates';
import { useAppDispatch, useAppSelector } from '../../common/hooks';
import { useEffect } from 'react';

export const InboundTemplates = () => {
  const dispatch = useAppDispatch()
  const { loading, templates } = useAppSelector(getTemplatesState);

  useEffect(()=>{
    dispatch(fetchTemplates())
  }, [dispatch])

  return (
    <div id="templates" className="tab-content active">
      <div className="section">
        <h2>Add Template</h2>
        <AddTemplate />
      </div>

      <div className="section">
        <h2>Templates List</h2>
        <div id="templatesList" className="loading">
          {loading && 'Loading...'}
          {templates.length ? (
            <TemplateList templates={templates}/>
          ) : (
            <p>No templates found</p>
          )}
        </div>
      </div>
    </div>
  );
};

export const InboundTemplatesRoute: RouteObject = {
  path: '/inbound-templates',
  Component: InboundTemplates,
};