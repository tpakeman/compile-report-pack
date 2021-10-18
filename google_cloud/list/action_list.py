
import json
EXECUTE_URL = 'REPLACE_ME'
def action_list(request):
    """Returns a list of integrations"""
    if request.method == 'POST':
      integrations = {"label": "Example Actions", "integrations": [{
        'name': 'compile_report_pack',
        'label': 'Compile Report Pack',
        'description': 'Bundles dashboards in a board into a single report',
        'supported_action_types': ['query'],
        'supported_formats': ['json'],
        'supported_formattings': ['unformatted'],
        'supported_visualization_formattings': ['noapply'], 
        'url': f'{EXECUTE_URL}/execute',
        'form_url': f'{EXECUTE_URL}/form'
      }]}
      return json.dumps(integrations)
    else:
      return json.dumps({'message': 'Method must be POST'}, 405)
      
  