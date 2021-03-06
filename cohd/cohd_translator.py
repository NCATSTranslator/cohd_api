"""
Implementation of the NCATS Biodmedical Data Translator TRAPI Spec
https://github.com/NCATS-Tangerine/NCATS-ReasonerStdAPI/tree/master/API
"""

from flask import jsonify
from semantic_version import Version

from . import cohd_trapi_093
from . import cohd_trapi_100
from .cohd_trapi import BiolinkConceptMapper, SriNodeNormalizer, map_omop_domain_to_blm_class
from .query_cohd_mysql import omop_concept_definitions


def translator_predicates():
    """ Implementation of /translator/predicates for Translator Reasoner API

    Returns
    -------
    json response object
    """
    return jsonify({
        'biolink:ChemicalSubstance': {
            'biolink:ChemicalSubstance': ['biolink:correlated_with'],
            'biolink:DiseaseOrPhenotypicFeature': ['biolink:correlated_with'],
            'biolink:Drug': ['biolink:correlated_with'],
            'biolink:Procedure': ['biolink:correlated_with'],
            'biolink:PopulationOfIndividualOrganisms': ['biolink:correlated_with']
        },
        'biolink:DiseaseOrPhenotypicFeature': {
            'biolink:ChemicalSubstance': ['biolink:correlated_with'],
            'biolink:DiseaseOrPhenotypicFeature': ['biolink:correlated_with'],
            'biolink:Drug': ['biolink:correlated_with'],
            'biolink:Procedure': ['biolink:correlated_with'],
            'biolink:PopulationOfIndividualOrganisms': ['biolink:correlated_with']
        },
        'biolink:Drug': {
            'biolink:ChemicalSubstance': ['biolink:correlated_with'],
            'biolink:DiseaseOrPhenotypicFeature': ['biolink:correlated_with'],
            'biolink:Drug': ['biolink:correlated_with'],
            'biolink:Procedure': ['biolink:correlated_with'],
            'biolink:PopulationOfIndividualOrganisms': ['biolink:correlated_with']
        },
        'biolink:Procedure': {
            'biolink:ChemicalSubstance': ['biolink:correlated_with'],
            'biolink:DiseaseOrPhenotypicFeature': ['biolink:correlated_with'],
            'biolink:Drug': ['biolink:correlated_with'],
            'biolink:Procedure': ['biolink:correlated_with'],
            'biolink:PopulationOfIndividualOrganisms': ['biolink:correlated_with']
        },
        'biolink:PopulationOfIndividualOrganisms': {
            'biolink:ChemicalSubstance': ['biolink:correlated_with'],
            'biolink:DiseaseOrPhenotypicFeature': ['biolink:correlated_with'],
            'biolink:Drug': ['biolink:correlated_with'],
            'biolink:Procedure': ['biolink:correlated_with'],
            'biolink:PopulationOfIndividualOrganisms': ['biolink:correlated_with']
        },
    })


def translator_query(request, version=None):
    """ Implementation of query endpoint for TRAPI

    Calls the requested version of the TRAPI message

    Parameters
    ----------
    request - flask request object
    version - string: TRAPI version

    Returns
    -------
    Response message with JSON data in Translator Reasoner API Standard or error status response for unsupported
    requested version
    """
    if version is None:
        version = '1.0.0'

    try:
        version = Version(version)
    except ValueError:
        return f'TRAPI version {version} not supported. Please use semantic version specifier, e.g., 1.0.0', 400

    if Version('1.0.0-beta') <= version < Version('1.1.0'):
        trapi = cohd_trapi_100.CohdTrapi100(request)
        return trapi.operate()
    elif version == Version('0.9.3'):
        trapi = cohd_trapi_093.CohdTrapi093(request)
        return trapi.operate()
    else:
        return f'TRAPI version {version} not supported', 501


def biolink_to_omop(request):
    """ Map from biolink CURIEs to OMOP concepts

    Parameters
    ----------
    request: Flask request

    Returns
    -------
    json response like:
    {
        "MONDO:0001187": {
        "distance": 2,
        "omop_concept_id": 197508,
        "omop_concept_name": "Malignant tumor of urinary bladder"
    }
    """
    j = request.get_json()
    if j is not None and 'curies' in j and j['curies'] is not None and type(j['curies']) == list:
        curies = j['curies']
    else:
        return 'Bad request', 400

    concept_mapper = BiolinkConceptMapper()
    return jsonify(concept_mapper.map_to_omop(curies))


def omop_to_biolink(request):
    """ Map from OMOP IDs to Biolink CURIEs

    Parameters
    ----------
    request: Flask request

    Returns
    -------
    JSON response with OMOP IDs as keys and SRI Node Normalizer response as values
    """
    j = request.get_json()
    if j is not None and 'omop_ids' in j and j['omop_ids'] is not None and type(j['omop_ids']) == list:
        omop_id_input = j['omop_ids']
    else:
        return 'Bad request', 400

    # Input may be list of ints, strings, or curie format. Convert to ints
    omop_ids = list()
    for omop_id in omop_id_input:
        if type(omop_id) == int:
            omop_ids.append(omop_id)
        elif type(omop_id) == str:
            # Strip OMOP prefix
            if omop_id.lower()[:5] == 'omop:':
                omop_id = omop_id[5:]
            if omop_id.isdigit():
                omop_ids.append(int(omop_id))

    # Map to Biolink using OxO
    concept_mapper = BiolinkConceptMapper()
    concept_definitions = omop_concept_definitions(omop_ids)
    mappings = dict()
    for omop_id in omop_ids:
        if omop_id in concept_definitions:
            domain_id = concept_definitions[omop_id]['domain_id']
            concept_class_id = concept_definitions[omop_id]['concept_class_id']
            blm_category = map_omop_domain_to_blm_class(domain_id, concept_class_id, )
            mapping = concept_mapper.map_from_omop(omop_id, blm_category)
            mappings[omop_id] = mapping

    # Normalize with SRI Node Normalizer
    normalized_mappings = dict()
    curies = [x['target_curie'] for x in mappings.values() if x is not None]
    normalized_nodes = SriNodeNormalizer.get_normalized_nodes(curies)
    for omop_id in omop_ids:
        normalized_mapping = None
        if mappings[omop_id] is not None and normalized_nodes[mappings[omop_id]['target_curie']] is not None:
            normalized_mapping = normalized_nodes[mappings[omop_id]['target_curie']]
        normalized_mappings[omop_id] = normalized_mapping

    return jsonify(normalized_mappings)
