# -*- encoding: utf-8 -*-
import argparse
import sys
import traceback
import csv
from hashlib import md5
from yamlns import namespace as ns
import mailchimp_marketing as MailchimpMarketing
from consolemsg import step, error, success
from erppeek import Client
import dbconfig


ERP_CLIENT = Client(**dbconfig.erppeek)
MAILCHIMP_CLIENT = MailchimpMarketing.Client(
    dict(api_key=dbconfig.MAILCHIMP_APIKEY, server=dbconfig.MAILCHIMP_SERVER_PREFIX)
)

doit = False

def get_member_category_id():
    module = 'som_partner_account'
    semantic_id = 'res_partner_category_soci'
    IrModelData = ERP_CLIENT.model('ir.model.data')
    
    member_category_relation = IrModelData.get_object_reference(
        module, semantic_id
    )
    if member_category_relation:
        return member_category_relation[-1]

def get_mailchimp_list_id(list_name):
    all_lists = MAILCHIMP_CLIENT.lists.get_all_lists(
        fields=['lists.id,lists.name'],
        count=100
    )['lists']
    for l in all_lists:
        if l['name'] == list_name:
            return l['id']
    raise Exception("List: <{}> not found".format(list_name))


def read_data_from_csv(csv_file):
    with open(csv_file, 'rb') as f:
        reader = csv.reader(f, delimiter=';')
        header = reader.next()

        # check if file is utf8 + BOM
        if '\xef\xbb\xbf' in header[0]:
            raise IOError

        if len(header) == 1:
            reader = csv.reader(f, delimiter=',')
            header = header[0].split(',')

        csv_content = [ns(dict(zip(header, row))) for row in reader if row[0]]

    return csv_content


def get_subscriber_hash(email):
    subscriber_hash = md5(email.lower()).hexdigest()
    return subscriber_hash


def archive_clients_from_list(list_name, email_list):
    if not doit:
        return ""

    list_id = get_mailchimp_list_id(list_name)
    operations = []
    for email in email_list:
        operation = {
            "method": "DELETE",
            "path": "/lists/{list_id}/members/{subscriber_hash}".format(
                list_id=list_id,
                subscriber_hash=get_subscriber_hash(email)
            ),
            "operation_id": email,
        }
        operations.append(operation)
    payload = {
        "operations": operations
    }
    try:
        response = MAILCHIMP_CLIENT.batches.start(payload)
    except ApiClientError as error:
        msg = "An error occurred an archiving batch request, reason: {}"
        error(msg.format(error.text))
    else:
        batch_id = response['id']
        while response['status'] != 'finished':
            time.sleep(2)
            response = MAILCHIMP_CLIENT.batches.status(batch_id)

        step("Archived operation finished!!")
        step("Total operations: {}, finished operations: {}, errored operations: {}".format(
            response['total_operations'],
            response['finished_operations'],
            response['errored_operations']
        ))
        result_summary = requests.get(response['response_body_url'])
        result_summary.raise_for_status()
        return result_summary.content

def is_titular_partner_mail(email):

    email_ids = ERP_CLIENT.ResPartnerAddress.search([('email', '=', email)])
    if not email_ids:
        return False
    partners_ids = [
        item['partner_id'][0]
        for item in ERP_CLIENT.ResPartnerAddress.read(email_ids, ['partner_id'])
        if item and 'partner_id' in item and item['partner_id']
    ]

    polisses_ids = ERP_CLIENT.GiscedataPolissa.search([('titular','in',partners_ids)])
    if not polisses_ids:
        return False

    return True

def is_soci_partner_mail(email, category_id):
    email_ids = ERP_CLIENT.ResPartnerAddress.search([('email', '=', email)])
    if not email_ids:
        return False

    partners_ids = [
        item['partner_id'][0]
        for item in ERP_CLIENT.ResPartnerAddress.read(email_ids, ['partner_id'])
        if item and 'partner_id' in item and item['partner_id']
    ]
    if not partners_ids:
        return False

    member_ids = ERP_CLIENT.ResPartner.search([
        ('category_id', 'in', [category_id]),
        ('id', 'in', partners_ids)
    ])

    if not member_ids:
        return False
    return True

def get_soci_no_soci(emails):
    to_archive = []
    total = len(emails)
    category_id = get_member_category_id()
    for counter, email in enumerate(emails):
        if not is_soci_partner_mail(email, category_id):
            to_archive.append(email)
            step("{}/{} - {} --> soci no soci", counter+1, total, email)
        else:
            step("{}/{} - {} --> soci", counter+1, total, email)
    return to_archive

def main(list_name, mailchimp_export_file, output):

    csv_data = read_data_from_csv(mailchimp_export_file)
    step("{} lines read from input csv", len(csv_data))

    mails = [item['Email Address'] for item in csv_data]
    step("{} emails extracted from input csv", len(mails))

    to_archive = get_soci_no_soci(mails)
    step("{} emails to archive found", len(to_archive))

    result = ''
    if doit:
        step("archiving...")
        result = archive_clients_from_list(list_name.strip(), to_archive)

    step("storing result {}", len(result))
    with open(mailchimp_export_file, 'w') as f:
        f.write(result)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            description=''
    )

    parser.add_argument(
        '--list',
        dest='list_name',
        required=True,
        help="nom de la llista de mailchimp"
    )

    parser.add_argument(
        '--mailchimp_export_file',
        dest='mailchimp_export_file',
        required=True,
        help="Fitxer amb export del mailchimp"
    )

    parser.add_argument(
        '--output',
        dest='output',
        required=True,
        help="Fitxer de sortida amb els resultats"
    )

    parser.add_argument(
        '--doit',
        type=bool,
        default=False,
        const=True,
        nargs='?',
        help='realitza les accions'
    )

    args = parser.parse_args()

    global doit
    doit = args.doit
    if doit:
        success("Es faran canvis a les polisses (--doit)")
    else:
        success("No es faran canvis a les polisses (sense opció --doit)")

    try:
        main(args.list_name, args.mailchimp_export_file, args.output)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        error("El proceso no ha finalizado correctamente: {}", str(e))
    else:
        success("Script finalizado")
