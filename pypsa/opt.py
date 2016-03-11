

## Copyright 2015-2016 Tom Brown (FIAS), Jonas Hoersch (FIAS)

## This program is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License as
## published by the Free Software Foundation; either version 3 of the
## License, or (at your option) any later version.

## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.

## You should have received a copy of the GNU General Public License
## along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Tools to override slow Pyomo problem building.

Essentially this library replaces Pyomo expressions with more strict
objects with a pre-defined structure, to avoid Pyomo having to think.

"""

# make the code as Python 3 compatible as possible
from __future__ import print_function, division
from __future__ import absolute_import
from six.moves import range


from pyomo.environ import Constraint, Objective

import pyomo


__author__ = "Tom Brown (FIAS), Jonas Hoersch (FIAS)"
__copyright__ = "Copyright 2015-2016 Tom Brown (FIAS), Jonas Hoersch (FIAS), GNU GPL 3"


class LExpression(object):
    """Affine expression of optimisation variables.

    Affine expression of the form:

    constant + coeff1*var1 + coeff2*var2 + ....

    Parameters
    ----------
    variables : list of tuples of coefficients and variables
        e.g. [(coeff1,var1),(coeff2,var2),...]
    constant : float

    """

    def __init__(self,variables=None,constant=0.):

        if variables is None:
            self.variables = []
        else:
            self.variables = variables

        self.constant = constant

    def __repr__(self):
        return "{} + {}".format(self.variables, self.constant)


    def __mul__(self,constant):
        try:
            constant = float(constant)
        except:
            print("Can only multiply an LExpression with a float!")
            return None
        return LExpression([(constant*item[0],item[1]) for item in self.variables],
                           constant*self.constant)

    def __rmul__(self,constant):
        return self.__mul__(constant)

    def __add__(self,other):
        if type(other) is LExpression:
            return LExpression(self.variables + other.variables,self.constant+other.constant)
        else:
            try:
                constant = float(other)
            except:
                print("Can only add an LExpression to another LExpression or a constant!")
                return None
            return LExpression(self.variables[:],self.constant+constant)


    def __radd__(self,other):
        return self.__add__(other)

    def __pos__(self):
        return self

    def __neg__(self):
        return -1*self

class LConstraint(object):
    """Constraint of optimisation variables.

    Linear constraint of the form:

    lhs sense rhs

    Parameters
    ----------
    lhs : LExpression
    sense : string
    rhs : LExpression

    """

    def __init__(self,lhs=None,sense="==",rhs=None):

        if lhs is None:
            self.lhs = LExpression()
        else:
            self.lhs = lhs

        self.sense = sense

        if rhs is None:
            self.rhs = LExpression()
        else:
            self.rhs = rhs

    def __repr__(self):
        return "{} {} {}".format(self.lhs, self.sense, self.rhs)


def l_constraint(model,name,constraints,*args):
    """A replacement for pyomo's Constraint that quickly builds linear
    constraints.

    Instead of

    model.name = Constraint(index1,index2,...,rule=f)

    call instead

    l_constraint(model,name,constraints,index1,index2,...)

    where constraints is a dictionary of constraints of the form:

    constraints[i] = [[(coeff1,var1),(coeff2,var2),...],sense,constant_term]

    i.e. the first argument is a list of tuples with the variables and their
    coefficients, the second argument is the sense string (must be one of
    "==","<=",">=") and the third argument is the constant term (a float).

    Variables may be repeated with different coefficients, which pyomo
    will sum up.

    Parameters
    ----------
    model : pyomo.environ.ConcreteModel
    name : string
        Name of constraints to be constructed
    constraints : dict
        A dictionary of constraints (see format above)
    *args :
        Indices of the constraints

    """

    setattr(model,name,Constraint(*args,noruleinit=True))
    v = getattr(model,name)
    for i in v._index:
        c = constraints[i]
        if type(c) is LConstraint:
            variables = c.lhs.variables + [(-item[0],item[1]) for item in c.rhs.variables]
            sense = c.sense
            constant = c.rhs.constant - c.lhs.constant
        else:
            variables = c[0]
            sense = c[1]
            constant = c[2]

        v._data[i] = pyomo.core.base.constraint._GeneralConstraintData(None,v)
        v._data[i]._body = pyomo.core.base.expr_coopr3._SumExpression()
        v._data[i]._body._args = [item[1] for item in variables]
        v._data[i]._body._coef = [item[0] for item in variables]
        v._data[i]._body._const = 0.
        if sense == "==":
            v._data[i]._equality = True
            v._data[i]._lower = pyomo.core.base.numvalue.NumericConstant(constant)
            v._data[i]._upper = pyomo.core.base.numvalue.NumericConstant(constant)
        elif sense == "<=":
            v._data[i]._equality = False
            v._data[i]._lower = None
            v._data[i]._upper = pyomo.core.base.numvalue.NumericConstant(constant)
        elif sense == ">=":
            v._data[i]._equality = False
            v._data[i]._lower = pyomo.core.base.numvalue.NumericConstant(constant)
            v._data[i]._upper = None


def l_objective(model,objective=None):
    """
    A replacement for pyomo's Objective that quickly builds linear
    objectives.

    Instead of

    model.objective = Objective(expr=sum(vars[i]*coeffs[i] for i in index)+constant)

    call instead

    l_objective(model,objective)

    where objective is an LExpression.

    Variables may be repeated with different coefficients, which pyomo
    will sum up.


    Parameters
    ----------
    model : pyomo.environ.ConcreteModel
    objective : LExpression

    """

    if objective is None:
        objective = LExpression()

    #initialise with a dummy
    model.objective = Objective(expr = 0.)

    model.objective._expr = pyomo.core.base.expr_coopr3._SumExpression()
    model.objective._expr._args = [item[1] for item in objective.variables]
    model.objective._expr._coef = [item[0] for item in objective.variables]
    model.objective._expr._const = objective.constant
