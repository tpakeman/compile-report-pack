import os, logging, base64, looker_sdk, json, re, time
from looker_sdk import models
from io import BytesIO
import sendgrid
from sendgrid.helpers.mail import Mail, Content, Attachment, FileContent, FileName, FileType, Disposition, ContentId
from PyPDF4 import PdfFileReader, PdfFileWriter
from pprint import pformat

PDF_SIZES = {'A3': {'height': 1120,'width': 1584},'A4': {'height': 986,'width': 1394}}
DEFAULT_PDF_PAGE_SIZE = 'A4'
DEFAULT_PDF_HEIGHT = PDF_SIZES[DEFAULT_PDF_PAGE_SIZE]['height']
DEFAULT_PDF_WIDTH = PDF_SIZES[DEFAULT_PDF_PAGE_SIZE]['width']
DEFAULT_PDF_IS_LANDSCAPE = True
USE_SCALING = False
SEND_EMAIL = True

logger = logging.getLogger('compile_report_pack')
logger.setLevel(logging.DEBUG)


def send_email(to_emails, subject, body, file_data, file_label, file_type=None, template_id=None):
    from_email = os.environ.get('SENDGRID_FROM_EMAIL')
    sg = sendgrid.SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
    content = Content('text/plain',body)
    ftype_mapping = {
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'pdf': 'application/pdf'
    }
    mail = Mail(from_email, to_emails, subject, content) 
    if file_data:
        logger.debug(file_data)
        # encode binary file so it can be JSON serialised for SendGrid call
        encoded = base64.b64encode(file_data.read()).decode()
        logger.debug(encoded)
        attachment = Attachment()
        attachment.file_content = FileContent(encoded)
        attachment.file_type = FileType(ftype_mapping[file_type])
        attachment.file_name = FileName(file_label)
        attachment.disposition = Disposition("attachment")
        attachment.content_id = ContentId("Example Content ID")
        mail.attachment = attachment
    if template_id:
        mail.template_id = template_id
    response = sg.send(mail) 
    return response


def form():
    """Form for the Compile Report Pack action: email details and pdf defaults (TBD)"""
    return json.dumps([
        {"name":'email_address',
            "label":'Email Address',
            "description":'Email address to send Report Pack in PDF format.',
            "required":True,},
        {"name":'email_subject',
            "label":'Subject',
            "description":'Email subject line',
            "required":True,},
        {"name":'email_body',
            "label":'Body',
            "description":'Email body text',
            "required":True,
            "type":'textarea'},
        {"name":'file_name',
            "label":'Report Pack Name',
            "description":'Filename for the generated PDF document',
            "required":True,}
        ])


def merge_pdfs(files):
    """Combine individually downloaded dashboard files into a compile report. Optionally scales the PDF."""
    tmpWrite = BytesIO()
    pdf_writer = PdfFileWriter()
    for file in files:
        pdf_reader = PdfFileReader(file[0])
        for idx in range(pdf_reader.getNumPages()):
            page = pdf_reader.getPage(idx)
            if USE_SCALING:
                if file[1] == 'A4':
                    logger.debug('scaling...')
                    page.scaleTo(812, 595) 
                else:
                    logger.debug('merge as is...')
            pdf_writer.addPage(page)
    pdf_writer.write(tmpWrite)
    return tmpWrite


def download_dashboard(sdk, dashboard_id, size=DEFAULT_PDF_PAGE_SIZE, filters=[]):
    if filters:
        filters = [f'{filter_[0]}={filter_[1]}' for filter_ in filters]
        filter_exp = '&'.join(filters)
    else:
        filter_exp = ''
    logger.debug(f'download_dashboard({dashboard_id}) with filter expression {filter_exp}')
    result = None
    try:
        height = PDF_SIZES[size]['height']
        width = PDF_SIZES[size]['width']
    except:
        logger.debug('FAILED to set height and width for PDF render')
        height = DEFAULT_PDF_HEIGHT
        width = DEFAULT_PDF_WIDTH        
    
    task = sdk.create_dashboard_render_task(
        dashboard_id= str(dashboard_id),
        result_format= 'pdf',
        body= models.CreateDashboardRenderTask(
            dashboard_style= 'tiled',
            dashboard_filters= filter_exp,
        ),
        height= height,
        width= width,
    )
    elapsed = 0.0
    delay = 0.5  # wait .5 seconds
    while True:
        poll = sdk.render_task(task.id)
        if poll.status == "failure":
            logger.warning(f'render failure: {poll}')
            return False
        elif poll.status == "success":
            result = BytesIO(sdk.render_task_results(task.id))
            logger.info(f"Render task completed in {elapsed} seconds")
            return result
        time.sleep(delay)
        elapsed += delay
   

def get_sdk_for_schedule(scheduled_plan_id):
    sdk = looker_sdk.init40()
    plan = sdk.scheduled_plan(scheduled_plan_id)
    sdk.login_user(plan.user_id)
    return sdk


def get_sdk_all_access():
    sdk = looker_sdk.init40()
    return sdk


def get_filters(sdk, look_id):
    result = sdk.run_look(look_id, 'json')
    return json.loads(result)


def action(payload):
    """Endpoint for the Compile Report Pack action."""
    sdk = get_sdk_all_access()
    data = json.loads(payload.get('attachment').get('data'))
    board_id = data[0]['board_id']
    report_pack = sdk.board(board_id)
    report_structure = []
    for section_id in report_pack.section_order[1:]:
        for section in report_pack.board_sections:
            if str(section.id) == str(section_id):
                report_section = {
                  'title': section.title,
                  'cover': '',
                  'pages': []
                }
                page_sizes = []
                for match in re.findall(r'\[(.*?)\]', section.title):
                    param, value = match.split(':')
                    if param == 'cover':
                        report_section['cover'] = value
                    if param == 'size':
                        page_sizes = value.split(',')
                logger.info(f'Processing section: {report_section}')
                logger.info(f'Page sizes config: {page_sizes}')
                
                page_num = 0
                filters = []
                for item_id in section.item_order:
                    for item in section.board_items:
                        if str(item.id) == str(item_id):
                            logger.debug(f'items loop, filters: {pformat(filters)}')
                            if item.look_id:
                                filters = get_filters(sdk, item.look_id)
                                logger.debug(pformat(filters))

                            if item.dashboard_id:
                                page = {
                                    'title': item.title,
                                    'dashboard_id': item.dashboard_id,
                                    'size': '',
                                    'orientation': '',
                                    'filters': filters
                                }
                                if page_sizes:
                                    page['size'] = page_sizes[min(page_num, len(page_sizes)-1)]
                                    page['orientation'] = 'landscape'
                                report_section['pages'].append(page)
                                page_num += 1
                                filters = []
                report_structure.append(report_section)

    logger.debug('Report Structure:')
    logger.debug(pformat(report_structure))

    pdfs_to_merge = []
    for section in report_structure:
        if section['cover']:
            pdfs_to_merge.append((section['cover'], 'A4'))
        for page in section['pages']:
            if 'size' in page.keys():
                if page['size']:
                    page_size = page['size']
                else:
                    page_size = DEFAULT_PDF_PAGE_SIZE
            if 'orientation' in page.keys():
                if page['orientation'] == 'landscape':
                    page_is_landscape = True
                elif page['orientation'] == 'portrait':
                    page_is_landscape = False
                else:
                    page_is_landscape = DEFAULT_PDF_IS_LANDSCAPE
            if page['filters']:
                page_dashboard_id = str(page['dashboard_id'])
                dashboard_filters = sdk.dashboard(page_dashboard_id).dashboard_filters
                filter_map = {}
                for filter_ in dashboard_filters:
                    filter_map[filter_.dimension] = filter_.name
                for idx, filter_set in enumerate(page['filters']):
                    logger.debug(f'idx filter_set {idx} {filter_set}')
                    filters = []
                    for dimension, value in filter_set.items():
                        try:
                            filters.append((filter_map[dimension], value))
                        except KeyError:
                            logger.debug(f'Ignoring filter value for {dimension} as not present in dashboard filter settings')
                    logger.debug(f'Downloading: {file_name} Size: {page_size} Is Landscape: {page_is_landscape}')
                    rendered = download_dashboard(sdk, page['dashboard_id'], page_size, filters)
                    if rendered:
                      pdfs_to_merge.append((rendered, page_size))
            else:
                file_name = page['title'].replace(' ', '_')
                logger.debug(f'Downloading: {file_name} Size: {page_size} Is Landscape: {page_is_landscape}')
                rendered = download_dashboard(sdk, page['dashboard_id'], page_size)
                pdfs_to_merge.append((rendered, page_size))
    
    report_pack_files = merge_pdfs(pdfs_to_merge)
    report_pack_files.seek(0)
    if SEND_EMAIL:
        form_params = payload.get('form_params')
        response = send_email(
            to_emails= form_params['email_address'],
            subject= form_params['email_subject'],
            body= form_params['email_body'],
            file_data= report_pack_files,
            file_label='compiled_report',
            file_type= 'pdf'
        )
    if response._status_code != 202:
        logger.error(response.__dict__)
    return {'response': response.__dict__}


def main(request):
    logger.info(f'Calling {request.path}')
    if request.path.endswith('form'):
        return form()
    else:
        return action(request.get_json())
