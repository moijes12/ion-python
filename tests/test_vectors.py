# Copyright 2016 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License.
# A copy of the License is located at:
#
#    http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS
# OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the
# License.

# Python 2/3 compatibility
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from collections import defaultdict
from decimal import getcontext
from functools import partial
from io import open, BytesIO
from itertools import chain
from os import listdir
from os.path import isfile, join, abspath, split

import six
from pytest import raises

from amazon.ion.exceptions import IonException
from amazon.ion.equivalence import ion_equals
from amazon.ion.simpleion import load, dump
from amazon.ion.util import Enum
from tests import parametrize


# This file lives in the tests/ directory. Up one level is tests/ and up another level is the package root, which
# contains the vectors/ directory.
_VECTORS_ROOT = abspath(join(abspath(__file__), u'..', u'..', u'vectors', u'iontestdata'))
_GOOD_SUBDIR = join(_VECTORS_ROOT, u'good')
_BAD_SUBDIR = join(_VECTORS_ROOT, u'bad')
_GOOD_TIMESTAMP_SUBDIR = join(_GOOD_SUBDIR, u'timestamp')
_BAD_TIMESTAMP_SUBDIR = join(_BAD_SUBDIR, u'timestamp')
_EQUIVS_TIMELINE_SUBDIR = join(_GOOD_TIMESTAMP_SUBDIR, u'equivTimeline')
_EQUIVS_SUBDIR = join(_GOOD_SUBDIR, u'equivs')
_EQUIVS_UTF8_SUBDIR = join(_EQUIVS_SUBDIR, u'utf8')
_BAD_UTF8_SUBDIR = join(_BAD_SUBDIR, u'utf8')
_NONEQUIVS_SUBDIR = join(_GOOD_SUBDIR, u'non-equivs')

_embedded_documents_annotation = u'embedded_documents'


_good_file = partial(join, _GOOD_SUBDIR)
_bad_file = partial(join, _BAD_SUBDIR)
_equivs_file = partial(join, _EQUIVS_SUBDIR)
_equivs_utf8_file = partial(join, _EQUIVS_UTF8_SUBDIR)
_nonequivs_file = partial(join, _NONEQUIVS_SUBDIR)
_equivs_timeline_file = partial(join, _EQUIVS_TIMELINE_SUBDIR)


_ENCODING_UTF8 = 'utf-8'
_ENCODING_UTF16_BE = 'utf-16-be'
_ENCODING_UTF32_BE = 'utf-32-be'

_FILE_ENCODINGS = defaultdict(lambda: _ENCODING_UTF8)
_FILE_ENCODINGS[_good_file(u'utf16.ion')] = _ENCODING_UTF16_BE
_FILE_ENCODINGS[_good_file(u'utf32.ion')] = _ENCODING_UTF32_BE

# Set these Decimal limits arbitrarily high because some test vectors require it. If users need decimals this large,
# they'll have to do this in their code too.
getcontext().Emax = 100000000000000000
getcontext().Emin = -100000000000000000
getcontext().prec = 100000


def _open(file):
    is_binary = file[-3:] == u'10n'
    if is_binary:
        return open(file, 'rb')
    else:
        return open(file, mode='r', encoding=_FILE_ENCODINGS[file])

_SKIP_LIST = (
    # TEXT:
    _good_file(u'subfieldVarUInt.ion'),  # TODO amznlabs/ion-python#34
    _good_file(u'subfieldVarUInt32bit.ion'),  # TODO amznlabs/ion-python#34
    _good_file(u'item1.10n'),  # TODO amznlabs/ion-python#46
    _nonequivs_file(u'symbolTablesUnknownText.ion'),  # TODO amznlabs/ion-python#46
    _equivs_file(u'timestampsLargeFractionalPrecision.ion'),  # TODO amznlabs/ion-python#35
    _equivs_file(u'structsFieldsRepeatedNames.ion'),  # TODO amznlabs/ion-python#36
    _nonequivs_file(u'structs.ion'),  # TODO amznlabs/ion-python#36
    # BINARY:
    _bad_file(u'container_length_mismatch.10n'),  # TODO amznlabs/ion-python#37
    _bad_file(u'emptyAnnotatedInt.10n'),  # TODO amznlabs/ion-python#37
    _good_file(u'structAnnotatedOrdered.10n'),  # TODO amznlabs/ion-python#38
    _good_file(u'structOrdered.10n'),  # TODO amznlabs/ion-python#38
)

_DEBUG_WHITELIST = (
    # Place files here to run only their tests.
)


class _VectorType(Enum):
    GOOD = 0
    GOOD_EQUIVS = 2
    GOOD_NONEQUIVS = 3
    GOOD_EQUIVS_TIMESTAMP_INSTANTS = 4
    GOOD_ROUNDTRIP = 5
    GOOD_EQUIVS_ROUNDTRIP = 6
    GOOD_NONEQUIVS_ROUNDTRIP = 7
    GOOD_EQUIVS_TIMESTAMP_INSTANTS_ROUNDTRIP = 8
    BAD = 9

    @property
    def thunk_generator(self):
        if self is _VectorType.GOOD_EQUIVS_ROUNDTRIP:
            return _equivs_roundtrip_thunks
        if self is _VectorType.GOOD_NONEQUIVS_ROUNDTRIP:
            return _nonequivs_roundtrip_thunks
        if self is _VectorType.GOOD_EQUIVS_TIMESTAMP_INSTANTS_ROUNDTRIP:
            return _equivs_roundtrip_timestamps_instants_thunks
        if self is _VectorType.GOOD:
            return _good_thunk
        if self is _VectorType.BAD:
            return _bad_thunk
        if self is _VectorType.GOOD_EQUIVS:
            return _equivs_thunks
        if self is _VectorType.GOOD_NONEQUIVS:
            return _nonequivs_thunks
        assert self is _VectorType.GOOD_EQUIVS_TIMESTAMP_INSTANTS
        return _equivs_timestamps_instants_thunks

    @property
    def comparison_param_generator(self):
        if self is _VectorType.GOOD_ROUNDTRIP:
            return _roundtrip_params
        if self is _VectorType.GOOD_EQUIVS_ROUNDTRIP:
            return _good_equivs_roundtrip_params
        if self is _VectorType.GOOD_NONEQUIVS_ROUNDTRIP:
            return _good_nonequivs_roundtrip_params
        if self is _VectorType.GOOD_EQUIVS_TIMESTAMP_INSTANTS_ROUNDTRIP:
            return _good_equivs_timestamps_instants_roundtrip_params
        if self is _VectorType.GOOD_EQUIVS:
            return _good_equivs_params
        if self is _VectorType.GOOD_NONEQUIVS:
            return _good_nonequivs_params
        assert self is _VectorType.GOOD_EQUIVS_TIMESTAMP_INSTANTS
        return _good_equivs_timestamps_instants_params


class _Parameter:
    def __init__(self, vector_type, file_path, test_thunk, desc=''):
        self.vector_type = vector_type
        # For more succinct error messages, shorten the absolute file paths so that they start from good/ or bad/.
        shortened_path = u''
        first = True
        while True:
            firsts, last = split(file_path)
            shortened_path = last if first else join(last, shortened_path)
            if last == u'good' or last == u'bad':
                break
            file_path = firsts
            first = False
        self.file_path = shortened_path
        self.test_thunk = test_thunk
        self.desc = '%s - %s %s' % (vector_type.name, shortened_path, desc)

    def __str__(self):
        return self.desc

_P = _Parameter
_T = _VectorType


def _list_files(directory_path):
    for file in listdir(directory_path):
        file_path = join(directory_path, file)
        if _DEBUG_WHITELIST:
            if file_path in _DEBUG_WHITELIST:
                yield file_path
        elif isfile(file_path) and file_path not in _SKIP_LIST:
            yield file_path


def _good_thunk(file):
    def good():
        with _open(file) as vector:
            load(vector, single_value=False)
    return good


def _bad_thunk(file):
    def bad():
        with _open(file) as vector:
            with raises((IonException, ValueError, TypeError)):
                load(vector, single_value=False)
    return bad


def _basic_params(vector_type, directory_path):
    for file in _list_files(directory_path):
        yield _P(vector_type, file, vector_type.thunk_generator(file))


def _equivs_thunk(a, b, timestamps_instants_only):
    def assert_equal():
        assert ion_equals(a, b, timestamps_instants_only)
    return assert_equal


def _equivs_thunks(a, b, timestamps_instants_only=False):
    yield _equivs_thunk(a, b, timestamps_instants_only)

_equivs_timestamps_instants_thunks = partial(_equivs_thunks, timestamps_instants_only=True)


def _nonequivs_thunk(a, b):
    def assert_nonequal():
        assert not ion_equals(a, b)
    return assert_nonequal


def _nonequivs_thunks(a, b):
    yield _nonequivs_thunk(a, b)


def _roundtrip_pairs(a, b):
    for is_a_binary in (None, True, False):
        for is_b_binary in (None, True, False):
            if is_a_binary is None and is_b_binary is None:
                continue  # This case is covered during the non-roundtrip comparison tests.
            if is_a_binary is not None:
                a = _roundtrip(a, is_a_binary)
            if is_b_binary is not None:
                b = _roundtrip(b, is_b_binary)
            yield a, b


def _equivs_roundtrip_thunks(a, b, timestamps_instants_only=False):
    for (a_roundtripped, b_roundtripped) in _roundtrip_pairs(a, b):
        yield _equivs_thunk(a_roundtripped, b_roundtripped, timestamps_instants_only)

_equivs_roundtrip_timestamps_instants_thunks = partial(_equivs_roundtrip_thunks, timestamps_instants_only=True)


def _nonequivs_roundtrip_thunks(a, b):
    for (a_roundtripped, b_roundtripped) in _roundtrip_pairs(a, b):
        yield _nonequivs_thunk(a_roundtripped, b_roundtripped)


def _element_preprocessor(ion_sequence):
    # Equivs/nonequivs sequences annotated with "embedded_documents" are sequences of strings that contain Ion data.
    # These strings need to be parsed before comparison.
    def preprocess(element):
        if is_embedded:
            assert isinstance(element, six.text_type)
            element = load(six.StringIO(element), single_value=False)
        return element
    is_embedded = ion_sequence.ion_annotations and \
        ion_sequence.ion_annotations[0].text == _embedded_documents_annotation
    return preprocess


def _equivs_params(vector_type, file, ion_sequence):
    preprocess = _element_preprocessor(ion_sequence)
    previous = preprocess(ion_sequence[0])
    for value in ion_sequence:
        value = preprocess(value)
        for thunk in vector_type.thunk_generator(previous, value):
            yield _P(vector_type, file, thunk, desc='%r == %r' % (previous, value))
        previous = value

_good_equivs_params = partial(_equivs_params, _T.GOOD_EQUIVS)
_good_equivs_timestamps_instants_params = partial(_equivs_params, _T.GOOD_EQUIVS_TIMESTAMP_INSTANTS)
_good_equivs_roundtrip_params = partial(_equivs_params, _T.GOOD_EQUIVS_ROUNDTRIP)
_good_equivs_timestamps_instants_roundtrip_params = partial(_equivs_params, _T.GOOD_EQUIVS_TIMESTAMP_INSTANTS_ROUNDTRIP)


def _nonequivs_params(vector_type, file, ion_sequence):
    preprocess = _element_preprocessor(ion_sequence)
    for i in range(len(ion_sequence)):
        for j in range(len(ion_sequence)):
            if i == j:
                continue
            a = preprocess(ion_sequence[i])
            b = preprocess(ion_sequence[j])
            for thunk in vector_type.thunk_generator(a, b):
                yield _P(vector_type, file, thunk, desc='%r != %r' % (a, b))

_good_nonequivs_params = partial(_nonequivs_params, _T.GOOD_NONEQUIVS)
_good_nonequivs_roundtrip_params = partial(_nonequivs_params, _T.GOOD_NONEQUIVS_ROUNDTRIP)


def _roundtrip(value, is_binary):
    out = BytesIO()
    dump(value, out, binary=is_binary)
    out.seek(0)
    roundtripped = load(out)
    return roundtripped


def _roundtrip_thunk(value, is_binary):
    def roundtrip():
        assert ion_equals(value, _roundtrip(value, is_binary))
    return roundtrip


def _roundtrip_params(file, value):
    for is_binary in (True, False):
        yield _P(_VectorType.GOOD_ROUNDTRIP, file, _roundtrip_thunk(value, is_binary),
                 desc='(%s) %r' % ('binary' if is_binary else 'text', value))


def _comparison_params(vector_type, directory_path):
    for file in _list_files(directory_path):
        with _open(file) as vector:
            sequences = load(vector, single_value=False)
        for sequence in sequences:
            for param in vector_type.comparison_param_generator(file, sequence):
                yield param


@parametrize(*chain(
    _basic_params(_T.GOOD, _GOOD_SUBDIR),
    _basic_params(_T.GOOD, _GOOD_TIMESTAMP_SUBDIR),
    _basic_params(_T.BAD, _BAD_SUBDIR),
    _basic_params(_T.BAD, _BAD_TIMESTAMP_SUBDIR),
    _basic_params(_T.BAD, _BAD_UTF8_SUBDIR),
))
def test_basic(p):
    """Tests basic (good/bad) reading without roundtrips. Because the data is lazily parsed, all tests are guaranteed
    to run, even if preceding tests fail.
    """
    p.test_thunk()


@parametrize(*chain(
    _comparison_params(_T.GOOD_EQUIVS_TIMESTAMP_INSTANTS, _EQUIVS_TIMELINE_SUBDIR),
    _comparison_params(_T.GOOD_EQUIVS, _EQUIVS_SUBDIR),
    _comparison_params(_T.GOOD_EQUIVS, _EQUIVS_UTF8_SUBDIR),
    _comparison_params(_T.GOOD_NONEQUIVS, _NONEQUIVS_SUBDIR),
))
def test_comparisons(p):
    """Tests comparisons (equivs/nonequivs). This is separate from `test_basic` because each Ion stream must be
    pre-parsed to generate the comparison pairs. Combining the two could cause some basic tests to not run in the event
    that one of these files fails to parse.
    """
    p.test_thunk()


@parametrize(*chain(
    _comparison_params(_T.GOOD_ROUNDTRIP, _GOOD_SUBDIR),
    _comparison_params(_T.GOOD_ROUNDTRIP, _GOOD_TIMESTAMP_SUBDIR),
    _comparison_params(_T.GOOD_EQUIVS_TIMESTAMP_INSTANTS_ROUNDTRIP, _EQUIVS_TIMELINE_SUBDIR),
    _comparison_params(_T.GOOD_EQUIVS_ROUNDTRIP, _EQUIVS_SUBDIR),
    _comparison_params(_T.GOOD_EQUIVS_ROUNDTRIP, _EQUIVS_UTF8_SUBDIR),
    _comparison_params(_T.GOOD_NONEQUIVS_ROUNDTRIP, _NONEQUIVS_SUBDIR),
))
def test_roundtrips(p):
    """Tests roundtrips of good files for equality. There will necessarily be failures in parameter generation for this
    test if there are failures in good files in `test_basic`. This is separate from `test_basic` because each Ion stream
    must be pre-parsed to generate the comparison pairs. Combining the two could cause some basic tests to not run in
    the event that one of these files fails to parse."""
    p.test_thunk()

