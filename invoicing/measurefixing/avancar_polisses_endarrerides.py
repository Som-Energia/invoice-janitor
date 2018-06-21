#!/usr/bin/env python
# -*- coding: utf8 -*-

from validacio_eines import (
    adelantar_polissa_endarerida,
    polisses_de_factures,
    contractOutOfBatchDate,
    lazyOOOP,
    draftContractInvoices,
    enviar_correu,
    showContract,
    open_and_send,
)
from consolemsg import step, fail, success, warn, error
from yamlns import namespace as ns

#####workaround validate ssl testing

import ssl

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    # Legacy Python that doesn't verify HTTPS certificates by default
    pass
else:
    # Handle target environment that doesn't support HTTPS verification
    ssl._create_default_https_context = _create_unverified_https_context

# definitions
O = lazyOOOP()
Contract = O.GiscedataPolissa
Measures = O.GiscedataLecturesLectura

step("Cercant polisses endarrerides")
polissaEndarrerida_ids = contractOutOfBatchDate()
polissaEndarrerida_ids_len = len(polissaEndarrerida_ids)
step("Adelantant {} polisses",polissaEndarrerida_ids_len)

_polissaEndarrerida_ids = [
    153397,
    154667,
]

polisses = Contract.read(polissaEndarrerida_ids,[
    'name',
    'data_alta',
    'tarifa',
    'comptadors',
    'data_ultima_lectura',
    'lot_facturacio',
    'pagador',
    ])

result = ns()
result.contractsWithPreviousDraftInvoices=[]
result.contractsWithError=[]
result.contractsForwarded=[]


for counter,polissa in enumerate(polisses):
    polissa = ns(polissa)
    step("{}/{} polissa {} ",counter, polissaEndarrerida_ids_len, polissa.name)
    showContract(polissa.id)

    drafInvoice_ids = draftContractInvoices(polissa.id)
    if drafInvoice_ids:
        warn("El contracte {id} ja tenia {n} factures en esborrany",
            n=len(drafInvoice_ids), **polissa)
        result.contractsWithPreviousDraftInvoices.append(polissa.id)
        continue

    step("\tInstantiate wizard")
    Wizard = O.WizardAvancarFacturacio
    wizcontext = dict(active_id = polissa.id)
    aWizard = Wizard.create({}, wizcontext)

    def debugWizard():
        print 'polissa_id', aWizard.polissa_id
        print 'data_inici', aWizard.data_inici
        print 'data_factura', aWizard.data_factura
        print 'data_ultima_lectura_original', aWizard.data_ultima_lectura_original
        print 'state:', aWizard.state
        print 'info:', aWizard.info

    data_inici_anterior = None

    while aWizard.data_inici != data_inici_anterior:

        data_inici_anterior = aWizard.data_inici

        step("\tGenerando factura para {}", aWizard.data_inici)
        aWizard.action_generar_factura()
        step("State: {0.state}\nInfo:\n{0.info}",
            aWizard)

        if aWizard.state != 'init': break

    generatedInvoice_ids = draftContractInvoices(polissa.id)
    success("\tFacturas generadas: {}", generatedInvoice_ids)
    Invoice = O.GiscedataFacturacioFactura

    #step("TODO: Call giscedata factura validation validator") 
    Validator = O.GiscedataFacturacioValidationValidator
    warning = O.GiscedataFacturacioValidationWarning
    step("\tValidando facturas...")
    validation_errors = [
        Validator.validate_invoice(invoice_id) 
        for invoice_id in generatedInvoice_ids
        ]
    for invoice_errors in validation_errors:
        for invoice_error in invoice_errors:
            step("\tDetected errors: {}", warning.read(invoice_error, ['message','name'])['name'])    
    step("\tValidation result {}", validation_errors)
    # TODO: filter out 'enrarecida' validations
    ko = any(validation_errors)
    if ko:
        error("Polissa que falla: {}", polissa.id)

    def clearDraftInvoices(polissa, invoice_ids, data_ultima_lectura_original):
        step("\tRemoving created invoices {}", invoice_ids)
        Invoice.unlink(invoice_ids, {})
        measures_ids = Measures.search([
            ('comptador','in', polissa.comptadors),
            ('name', '>', str(data_ultima_lectura_original)),
        ])
        step("\tRemoving created measures {}", measures_ids)
        if measures_ids:
            Measures.unlink(measures_ids, {})

    if ko:
        step("\tAnotate it as a failing case")
        result.contractsWithError.append(polissa.id)
    else:
        step("\tAnotate it as a forwarded case")
        result.contractsForwarded.append(polissa.id)

    if ko:
        clearDraftInvoices(polissa, generatedInvoice_ids, aWizard.data_ultima_lectura_original)
    else:
        if len(generatedInvoice_ids)>1:
            step("\tMore than one invoice, sending the warning email")
            enviar_correu(polissa.id, 71, 8,'giscedata.polissa')
        step("Open and send all the invoices")
        print 'polissa.id', polissa.id
        lang = O.ResPartner.read(polissa.pagador[0], ['lang'])['lang']
        # TODO: What if this fails? Mails already sent!
        open_and_send(generatedInvoice_ids, lang) 

    ignoreme = raw_input("Pulsa return para siguiente contrato")

success(result.dump())

success(u"""\
- Polisses avançades a data de lot:
    - {contractsForwarded} 

- Polisses que ja tenien factures en esborrany i s'han deixat
    - {contractsWithPreviousDraftInvoices}

- Polisses que no s'ha pogut validar les factures generades:
    - {contractsWithError}
""", **result)




# vim: et ts=4 sw=4
