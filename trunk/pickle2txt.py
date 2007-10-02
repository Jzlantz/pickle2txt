#!/usr/bin/env python
# -*- coding: iso-8859-15 -*-

##    This library is free software; you can redistribute it and/or
##    modify it under the terms of the GNU Lesser General Public
##    License as published by the Free Software Foundation; either
##    version 2.1 of the License, or (at your option) any later version.
##
##    This library is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
##    Lesser General Public License for more details.=
##
##    You should have received a copy of the GNU Lesser General Public
##    License along with this library; if not, write to the Free Software
##    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
##

"""Extracts an object from any pickled file and produces a text file.

This is a command-line tool for making sense of an otherwise abandoned Python
pickle file. 

Target formats:
    DataTree 
    JSON
    Python
    S-expressions (SXML)
    Plain text
    XML
    YAML

It's OK to specify more than one format. If no input files are given, the
script searches the current directory. If no options are given, the usage guide
is printed.

Authors: Eric Talevich & contributors (see code for credits)
License: GPL (http://www.gnu.org/copyleft/gpl.html)

"""

# TODO:
# It would be helpful to have a couple functions to navigate the object
# - One to flatten the tree/ return pairs
# - Another to navigate while keeping the structure (apply a mapping)
#
# Support the formats I claimed
#
# ENH: for formats that already have projects devoted to them, check to see if 
# the popular (faster) modules are available (e.g. simplejson). 
# If so, use them; if not, use this code.

import sys
import pickle


class WriteError(Exception): 
    pass


USAGE = """pickle2txt Usage

Command-line syntax: 
    pickle2txt [--xml | --json | --datatree | --txt] inpath outpath
    pickle2txt [-h | --help]
"""


# -----------------------------------------------------------------------------

class Format(object):

    def __init__(self):
        pass

    def write(self, obj, name):
        pass


# DataTree

class Format_datatree(Format):

    """Ivan Vecerina's data storage format, similar to JSON.

    Quirks:
     - Arrays are written with commas at the start of the next line, rather than
        at the end of the line containing the statement.
     - The last comma in an array or dictionary listing is not necessary, but 
        will not muck up this reader implementation. Will it muck up the C++ 
        and C implementations?

    """

    # ENH: Consider using repr() and replacement tricks as a shortcut

    import os
    from types import *
    from cStringIO import StringIO

    NL = os.linesep  # *surely* this is used in other classes, too?

    def __init__(self):
        """Creates an instance at the top level."""
        self.depth_ = 0

    def write(self, obj):
        """Serialize the given object and return as a string."""
        NL = "\n\r"
        dstlist = ["# DataTree text file" + 2*NL]
        dstlist.extend(self.setValue(obj.__dict__))
        dstlist.append(2*NL + "# EOF" + NL)
        return ''.join(dstlist)

    def setValue(self, val):
        """Calls the appropriate function to handle the given value.

        Recurses with setDictionary or setArray if the value is a dictionary or
        sequence.

        """
        valtype = type(val)
        if valtype in (ClassType, DictType):
            if valtype is ClassType:
                val = val.__dict__
            self.depth_ += 1
            ll = self.setDictionary(val)
        elif valtype in (ListType, TupleType):
            self.depth_ += 1
            ll = self.setArray(val)
        else:
            ll = [self.serialize(val)]
        return ll


    def setDictionary(self, dc):
        """Converts a dictionary to a list for eventual serialization."""
        ll = ['{' + self.__class__.NL]
        for key in dc:
            ll.extend([key, ' : '] + self.setValue(dc[key]))
        ll.append('}'+ self.__class__.NL)
        return ll


    def setArray(self, arr):
        """Prepares a sequence for serialization by inserting delimiters."""
        # TODO: Arrays should be all on one line
        ll = ["("]
        for val in arr:
            ll.extend(self.setValue(val))
            ll.append(', ') # Avoid double commas
        ll.append(")" + self.__class__.NL)
        return ll


    def serialize(self, val):
        """Converts the given value to a string when value isn't a dict or sequence."""
        #TODO: indentation. Prepend a "\t"*depth to each new line.
        if isinstance(val, NoneType):
            val = "00"
        elif isinstance(val, BooleanType):
            val = val and "1" or "0"
        elif isinstance(val, StringTypes) and ' ' in val:
            val = "'%s'" % val
        elif type(val) in (IntType, LongType, FloatType, ComplexType):
            val = str(val)
        else:
            try:
                val = repr(val)
            except:
                raise WriteError, "Element '%s' cannot be serialized" % val.__name__
        return val + self.__class__.NL


# JSON

# Using minjson.py from the json-py project
# Copyright Jim Washington and Patrick D. Logan (LGPL license)
# http://sourceforge.net/projects/json-py/

##############################################################################
##
##    minjson.py implements JSON reading and writing in python.
##    Copyright (c) 2005 Jim Washington and Contributors.
##
##############################################################################

class Format_json(Format):

    """Javascript's native data storage format."""

    from re import compile, sub, search, DOTALL

    tfnTuple = (('True','true'),('False','false'),('None','null'),)

    # re for a double-quoted string that has a single-quote in it
    # but no double-quotes and python punctuation after:
    redoublequotedstring = compile(r'"[^"]*\'[^"]*"[,\]\}:\)]')
    escapedSingleQuote = r"\'"
    escapedDoubleQuote = r'\"'

    def write(self, obj, name, encoding="utf-8"):
        """Represent the object as a string.  
        
        Do any necessary fix-ups with pyexpr2jsexpr.
        
        """
        try:
            #not really sure encode does anything here
            aString = str(obj).encode(encoding)
        except UnicodeEncodeError:
            aString = obj.encode(encoding)
        if isinstance(obj,basestring):
            if '"' in aString:
                aString = aString.replace(escapedDoubleQuote,'"')
                result = '"%s"' % aString.replace('"',escapedDoubleQuote)
            else:
                result = '"%s"' % aString
        else:
            result = _pyexpr2jsexpr(aString).encode(encoding)
        return result

    def _pyexpr2jsexpr(aString):
        """Use python's formatting of string representations of objects.  
        
        Python always uses "'" to delimit strings.  Except it doesn't when
        there is ' in the string.  Fix that, then, if we split on that
        delimiter, we have a list that alternates non-string text with string
        text.  Since string text is already properly escaped, we only need to
        replace True, False, and None in non-string text and remove any unicode
        'u's preceding string values.

        """
        inSingleQuote = False
        inDoubleQuote = False
        #python will quote with " when there is a ' in the string,
        #so fix that first
        if redoublequotedstring.search(aString):
            aString = doQuotesSwapping(aString)
        marker = None
        if escapedSingleQuote in aString:
            #replace escaped single quotes with a marker
            marker = markerBase = '|'
            markerCount = 1
            while marker in aString:
                #if the marker is already there, make it different
                markerCount += 1
                marker = markerBase * markerCount
            aString = aString.replace(escapedSingleQuote,marker)

        #escape double-quotes
        aString = aString.replace('"',escapedDoubleQuote)
        #split the string on the real single-quotes
        splitStr = aString.split("'")
        outList = []
        alt = True
        for subStr in splitStr:
            #if alt is True, non-string; do replacements
            if alt:
                subStr = _handleCode(subStr)
            outList.append(subStr)
            alt = not alt
        result = '"'.join(outList)
        if marker:
            #put the escaped single-quotes back as "'"
            result = result.replace(marker,"'")
        return result

    def doQuotesSwapping(aString):
        """Rewrite double-quoted strings with single quotes as single-quoted
        strings with escaped single quotes."""
        s = []
        foundlocs = redoublequotedstring.finditer(aString)
        prevend = 0
        for loc in foundlocs:
            start,end = loc.span()
            s.append(aString[prevend:start])
            tempstr = aString[start:end]
            endchar = tempstr[-1]
            ts1 = tempstr[1:-2]
            ts1 = ts1.replace("'",escapedSingleQuote)
            ts1 = "'%s'%s" % (ts1,endchar)
            s.append(ts1)
            prevend = end
        s.append(aString[prevend:])
        return ''.join(s)

    def _replaceTrueFalseNone(aString):
        """Replace True, False, and None with javascript counterparts"""
        for k in tfnTuple:
            if k[0] in aString:
                aString = aString.replace(k[0],k[1])
        return aString

    def _handleCode(subStr):
        """Replace True, False, and None with javascript counterparts if
        appropriate, remove unicode u's, fix long L's, make tuples lists, and
        strip white space if requested
        """
        if 'e' in subStr:
            #True, False, and None have 'e' in them. :)
            subStr = (_replaceTrueFalseNone(subStr))
        if subStr[-1] in "uU":
            #remove unicode u's
            subStr = subStr[:-1]
        if "L" in subStr:
            #remove Ls from long ints
            subStr = subStr.replace("L",'')
        #do tuples as lists
        if "(" in subStr:
            subStr = subStr.replace("(",'[')
        if ")" in subStr:
            subStr = subStr.replace(")",']')
        return subStr


# Python code

class Format_py(Format):

    """Python code representation via the pprint module."""

    def write(self, obj):
        from pprint import pprint
        import cStringIO
        output = cStringIO.StringIO()
        pprint.pprint(obj, stream=output, indent=4)
        contents = output.getvalue()
        output.close()
        return contents


# S-Expressions (Lisp/SXML)

class Format_lisp(Format):

    """S-expressions, a.k.a. Lisp code. Specifically, SXML."""

    def dict2sexp(self, dc, root='Root', indent='\t'):
        """Convert a dictionary to an SXML string.

        Rules:
            int, float -> as-is
            string -> "string"
            dict -> (key value)
            tuple, list -> repeat tag for each value
            bool -> int(bool)
            None, empty string -> empty node
            other object -> str(obj)

        """
        from xml.sax.saxutils import escape

        def tagset(key, val, level):
            if val in (None, ""):
                return "%s(%s \"\")\n" % (indent*level, key)

            if type(val) in (list, tuple):
                return "".join(tagset(key, v, level) for v in val)

            if type(val) is bool: 
                val = int(val)

            return "%s(%s %s)\n" % (indent*level, key, 
                                    format_value(key, val, level))

        def format_value(key, val, level):
            if type(val) in (float, int):
                pass

            elif type(val) is dict:
                ll = [tagset(k, v, level+1) for k, v in val.iteritems()]
                ll.sort()  # NB: Py dicts are unordered
                val = "\n%s%s" % (''.join(ll), indent*level)

            else:
                val = '"%s"' % val

            return val

        return tagset(root, dc, 0)

    def write(self, obj):
        return '(*TOP* (*PI* xml "version=\"1.0\" encoding=\"UTF-8\"")\n' + \
                self.dict2sexp(obj.__dict__, root=__name__) + ')\n'


# Plain text

class Format_text(Format)::

    """ Prints all attributes as simple "Attribute: Value\n" pairs """

    def write(self, obj):
        # Recursively go through the object and flatten it, basically
        str = ''
        # TODO: recurse
        for key, val in obj.__dict___:
            str.join("%s: \t%s" % (key, val))
        return str


# XML

class Format_xml(Format):

    """Standard XML 1.0 using Python builtins."""


    def dict2xml(self, dc, root='Root', indent='\t'):
        """Convert a dictionary to an XML string.

        Rules:
            string -> escape(string)
            int, float -> as-is
            dict -> <key>value</key>
            tuple, list -> repeat tag for each value
            bool -> int(bool)
            None, empty string -> empty node
            other object -> escape(str(obj))

        """
        from xml.sax.saxutils import escape
        
        def tagset(key, val, level):
            if val in (None, ""):
                return "%s<%s />\n" % (indent*level, key)

            if type(val) in (list, tuple):
                return "".join(tagset(key, v, level) for v in val)

            if type(val) is bool: 
                val = int(val)

            return "%s<%s>%s</%s>\n" % (indent*level, key, 
                                        format_value(key, val, level), key)

        def format_value(key, val, level):
            if type(val) in (float, int, str):
                pass

            elif type(val) is dict:
                ll = [tagset(k, v, level+1) for k, v in val.iteritems()]
                ll.sort()  # NB: Py dicts are unordered
                val = "\n%s%s" % (''.join(ll), indent*level)

            elif type(val) is not str:
                val = str(val)

            return val

        return tagset(root, dc, 0)

    def write(self, obj):
        return '<?xml version="1.0" encoding="UTF-8">\n' + \
                dict2xml(obj.__dict__, root=__name__)


# YAML

class Format_yaml(Format):
    """Yet Another Markup Language."""
    # TODO:
    # Look for existing code

    def write(self, obj):
        pass

# -----------------------------------------------------------------------------

def flat_traversal(obj):
    pass




# -----------------------------------------------------------------------------

def to_format(obj, format, name):
    fmat = eval("Format_%s()" % format)
    return fmat.write(obj, name)


def main():
    """Command-line processing."""
    from optparse import OptionParser

    parser = OptionParser(USAGE)
    parser.add_option("-d", "--datatree", dest="to_datatree",
                        action="store_true",
                        help="Output in Ivan Vecerina's DataTree format")
    parser.add_option("-j", "--json", dest="to_json",
                        action="store_true",
                        help="Output in JSON format")
    parser.add_option("-p", "--py", dest="to_py",
                        action="store_true",
                        help="Output as a formatted Python code representation")
    parser.add_option("-t", "--text", dest="to_text",
                        action="store_true",
                        help="Output as plain, unformatted text")
    parser.add_option("-x", "--xml", dest="to_xml",
                        action="store_true",
                        help="Output in XML 1.0 format")
    parser.add_option("-y", "--yaml", dest="to_yaml",
                        action="store_true",
                        help="Output in YAML format")

    options, args = parser.parse_args()

    filepaths = []
    for arg in args:
        if os.path.isfile(arg):
            filepaths.append(arg)
        else:

    if not filepaths:
        print >>sys.stderr, "Warning: no input files given or found."
        return
        # ENH: operate on the files in the current directory?

    for path in filepaths:
        try:
            infile = open(path, 'r')
            obj = pickle.load(infile)
            infile.close()
        except IOError:
            pass # file didn't open, print some warning to sys.stderr
        except UnpickleError:
            pass # file wasn't a valid pickle file, print another warning to stderr

        for format in ("datatree", "json", "py", "text", "xml", "yaml"):
            if eval("options.to_" + format):
                outfile = file(path + '.' + format, 'w')
                str = to_format(obj, format, path)
                outfile.write(str)
                outfile.close()


if __name__is "__main__":
    main()

#EOF
