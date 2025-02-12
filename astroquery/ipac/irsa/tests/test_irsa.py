# Licensed under a 3-clause BSD style license - see LICENSE.rst

import os
import re
import numpy as np

import pytest
from astropy.table import Table
import astropy.coordinates as coord
import astropy.units as u

from astroquery.utils.testing_tools import MockResponse
from astroquery.utils import commons
from astroquery.ipac.irsa import Irsa, conf
from astroquery.ipac import irsa

DATA_FILES = {'Cone': 'Cone.xml',
              'Box': 'Box.xml',
              'Polygon': 'Polygon.xml'}

OBJ_LIST = ["m31", "00h42m44.330s +41d16m07.50s",
            commons.GalacticCoordGenerator(l=121.1743, b=-21.5733,
                                           unit=(u.deg, u.deg))]


def data_path(filename):
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    return os.path.join(data_dir, filename)


@pytest.fixture
def patch_get(request):
    try:
        mp = request.getfixturevalue("monkeypatch")
    except AttributeError:  # pytest < 3
        mp = request.getfuncargvalue("monkeypatch")
    mp.setattr(Irsa, '_request', get_mockreturn)
    return mp


def get_mockreturn(method, url, params=None, timeout=10, cache=False, **kwargs):
    filename = data_path(DATA_FILES[params['spatial']])
    content = open(filename, 'rb').read()
    return MockResponse(content, **kwargs)


@pytest.mark.parametrize(('dim'),
                         ['5d0m0s', 0.3 * u.rad, '5h0m0s', 2 * u.arcmin])
def test_parse_dimension(dim):
    # check that the returned dimension is always in units of 'arcsec',
    # 'arcmin' or 'deg'
    new_dim = irsa.core._parse_dimension(dim)
    assert new_dim.unit in ['arcsec', 'arcmin', 'deg']


@pytest.mark.parametrize(('ra', 'dec', 'expected'),
                         [(10, 10, '10 +10'),
                          (10.0, -11, '10.0 -11')
                          ])
def test_format_decimal_coords(ra, dec, expected):
    out = irsa.core._format_decimal_coords(ra, dec)
    assert out == expected


@pytest.mark.parametrize(('coordinates', 'expected'),
                         [("5h0m0s 0d0m0s", "75.0 +0.0")
                          ])
def test_parse_coordinates(coordinates, expected):
    out = irsa.core._parse_coordinates(coordinates)
    for a, b in zip(out.split(), expected.split()):
        try:
            a = float(a)
            b = float(b)
            np.testing.assert_almost_equal(a, b)
        except ValueError:
            assert a == b


def test_args_to_payload():
    out = Irsa._args_to_payload("fp_psc")
    assert out == dict(catalog='fp_psc', outfmt=3, outrows=conf.row_limit,
                       selcols='')


@pytest.mark.parametrize(("coordinates"), OBJ_LIST)
def test_query_region_cone_async(coordinates, patch_get):
    response = Irsa.query_region_async(
        coordinates, catalog='fp_psc', spatial='Cone',
        radius=2 * u.arcmin, get_query_payload=True)
    assert response['radius'] == 2
    assert response['radunits'] == 'arcmin'
    response = Irsa.query_region_async(
        coordinates, catalog='fp_psc', spatial='Cone', radius=2 * u.arcmin)
    assert response is not None


@pytest.mark.parametrize(("coordinates"), OBJ_LIST)
def test_query_region_cone(coordinates, patch_get):
    result = Irsa.query_region(
        coordinates, catalog='fp_psc', spatial='Cone', radius=2 * u.arcmin)

    assert isinstance(result, Table)


@pytest.mark.parametrize(("coordinates"), OBJ_LIST)
def test_query_region_box_async(coordinates, patch_get):
    response = Irsa.query_region_async(
        coordinates, catalog='fp_psc', spatial='Box',
        width=2 * u.arcmin, get_query_payload=True)
    assert response['size'] == 120
    response = Irsa.query_region_async(
        coordinates, catalog='fp_psc', spatial='Box', width=2 * u.arcmin)
    assert response is not None


@pytest.mark.parametrize(("coordinates"), OBJ_LIST)
def test_query_region_box(coordinates, patch_get):
    result = Irsa.query_region(
        coordinates, catalog='fp_psc', spatial='Box', width=2 * u.arcmin)

    assert isinstance(result, Table)


poly1 = [coord.SkyCoord(ra=10.1, dec=10.1, unit=(u.deg, u.deg)),
         coord.SkyCoord(ra=10.0, dec=10.1, unit=(u.deg, u.deg)),
         coord.SkyCoord(ra=10.0, dec=10.0, unit=(u.deg, u.deg))]
poly2 = [(10.1 * u.deg, 10.1 * u.deg), (10.0 * u.deg, 10.1 * u.deg),
         (10.0 * u.deg, 10.0 * u.deg)]


@pytest.mark.parametrize(("polygon"), [poly1, poly2])
def test_query_region_async_polygon(polygon, patch_get):
    response = Irsa.query_region_async(
        "m31", catalog="fp_psc", spatial="Polygon",
        polygon=polygon, get_query_payload=True)

    for a, b in zip(re.split("[ ,]", response["polygon"]),
                    re.split("[ ,]", "10.1 +10.1,10.0 +10.1,10.0 +10.0")):
        for a1, b1 in zip(a.split(), b.split()):
            a1 = float(a1)
            b1 = float(b1)
            np.testing.assert_almost_equal(a1, b1)

    response = Irsa.query_region_async(
        "m31", catalog="fp_psc", spatial="Polygon", polygon=polygon)

    assert response is not None


@pytest.mark.parametrize(("polygon"),
                         [poly1,
                          poly2,
                          ])
def test_query_region_polygon(polygon, patch_get):
    result = Irsa.query_region(
        "m31", catalog="fp_psc", spatial="Polygon", polygon=polygon)

    assert isinstance(result, Table)


@pytest.mark.parametrize(('spatial', 'result'),
                         zip(('Cone', 'Box', 'Polygon', 'All-Sky'),
                             ('Cone', 'Box', 'Polygon', 'NONE')))
def test_spatial_valdi(spatial, result):
    out = Irsa._parse_spatial(
        spatial, coordinates='m31', radius=5 * u.deg, width=5 * u.deg,
        polygon=[(5 * u.hour, 5 * u.deg)] * 3)
    assert out['spatial'] == result


@pytest.mark.parametrize(('spatial'), [('cone', 'box', 'polygon', 'all-Sky',
                                        'All-sky', 'invalid', 'blah')])
def test_spatial_invalid(spatial):
    with pytest.raises(ValueError):
        Irsa._parse_spatial(spatial, coordinates='m31')


def test_deprecated_namespace_import_warning():
    with pytest.warns(DeprecationWarning):
        import astroquery.irsa
