from erppeek import Client
from datetime import datetime,timedelta
import configdb

O = Client(**configdb.erppeek)

pol_obj = O.GiscedataPolissa
sw_obj = O.GiscedataSwitching

def contractesCIF(cif,tarifa,data):
    pol_obj = O.GiscedataPolissa
    pol_ids = pol_obj.search([('titular_nif','like',cif),
                    ('tarifa','=',tarifa),
                    ('data_firma_contracte','<',data)])
    return len(pol_ids)
                    


def contractesTarifa(tarifa,data):
    pol_obj = O.GiscedataPolissa
    sw_obj = O.GiscedataSwitching
    m101_obj = O.model('giscedata.switching.m1.01')
    
    #Polisses actived
    pol_ids = pol_obj.search([('tarifa.name','=',tarifa),
                       ('data_firma_contracte','<',data)])
    sol_pol = len(pol_ids)
    pol_reads = pol_obj.read(pol_ids, ['cups'])
    pol_cups_ids = [a['cups'][0] for a in pol_reads if a['cups']]
    
    
    #Polisses inactived
    pol_inactived_ids = pol_obj.search([('cups','not in',pol_cups_ids),
                                ('tarifa.name','=',tarifa),
                                 ('active','=',False),
                                 ('data_alta','!=', False),
                                 ('data_firma_contracte','<',data)])
    pol_inac = len(pol_inactived_ids)
    per_b = round(float(pol_inac)/float(sol_pol)*100,2)

    #Polisses en esborrany
    pol_draft_ids = pol_obj.search([('id','in',pol_ids),
                                    ('state','=','esborrany')])    
    pol_draft = len(pol_draft_ids)
    
    #Quan n'hi ha d'endarreits
    ## quants tenen el mail 3.0A al notificador
    ### Podem mirar quants n'hi ha mab C2

    
    #Segmentacio
    ccvv = contractesCIF('ESH',tarifa,data)
    coop = contractesCIF('ESF',tarifa,data)
    ass = contractesCIF('ESG',tarifa,data)
    
    #Modificacions de potencia
    sw_ids = sw_obj.search([('cups_id','in',pol_cups_ids),
                            ('proces_id.name','=','M1')])
    m1_ids = m101_obj.search([('sw_id','in',sw_ids),
                             ('sollicitudadm','in',['A','N'])])
    ### tenir en compte els c2 amb canvi de potencia
    m101 = len(m1_ids)
    per_m = round(float(m101)/float(sol_pol - pol_draft)*100,2)
    
    #Polisses amb facturacio endarrerida
    endarrerides_ids = pol_obj.search([('facturacio_endarrerida','=',True),
                                    ('id','in',pol_ids)])
    endarrerides = len(endarrerides_ids)
    

    #Resum 
    text_pol = 40*"=" + "\nContractes amb {tarifa}\n" + 40*"="
    text_pol += "\nSolicituds de contractes total: {sol_pol}"
    text_pol += "\n --> CCVV: {ccvv}"
    text_pol += "\n --> Cooperatives: {coop}"
    text_pol += "\n --> Associacions: {ass}"
    text_pol += "\nContractes en esborrany: {pol_draft} quan n'hi ha d'endearrerits?"
    text_pol += "\nContractes de baixa : {pol_inac} ({per_b}%)"
    text_pol += "\nModificacions de contractes: {m101} ({per_m}%)"
    text_pol += "\nPolisses amb facturacio endarerides: {endarrerides}"
    text_pol = text_pol.format(**locals())
    print text_pol

def resum_qc(text_evol):
    contractesTarifa('3.0A','2016-06-01')
    #contractesTarifa('3.1A')
    contractesNous('3.0A','2016-03-20')
    print "\nEvolucio de contractes mensual"
    print 40*"="
    print text_evol



#Contractes nous a la setmana
def contractesNous(tarifa, data):
    sense_not = []
    pol_ids = pol_obj.search([('tarifa.name','=',tarifa),
                       ('data_firma_contracte','>=',data)])
    sol_pol = len(pol_ids)
    pol_reads = pol_obj.read(pol_ids,
                        ['notificacio_email','cups'])
    for pol_read in pol_reads:
        if pol_read['notificacio_email'] != 'tarifa3.0@somenergia.coop':
            if pol_read['cups']:
                sense_not.append(pol_read['cups'][1])
    sense_not_ = len(sense_not)
    text_pnews = "Contractes Nous des de {data}: {sol_pol}"
    text_pnews += "\n Dels quals no ens han dit quina potencia volen: {sense_not_}"
    text_pnews += "\n   --> {sense_not}"
    text_pnews = text_pnews.format(**locals())
    print text_pnews
    
 


#Contractes nous al mes.

text_evol = "No implementat"


#Contractes que els hi hem fet modificacio

#Analisis de porta d'entrada. Formulari?

#Contractes en 3.1A

resum_qc(text_evol)

