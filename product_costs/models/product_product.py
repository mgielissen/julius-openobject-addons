# -*- coding: utf-8 -*-
###############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2016-Today Julius Network Solutions SARL <contact@julius.fr>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp import models, fields, api, _


class product_product_costs(models.Model):
    _name = 'product.product.costs'
    _description = 'Product variant costs'
    _order = 'sequence'

    name = fields.Char(related='type_id.name', readonly=True, store=True)
    sequence = fields.Integer(required=True)
    type_id = fields.Many2one('product.costs.type', 'Cost type',
                              required=True)
    type = fields.Selection([
                             ('fixed', 'Fixed price'),
                             ('bom', 'BoM'),
                             ('bom_routing', 'BoM Routing'),
                             ('python', 'Python Computation'),
                             ('formula', 'Formula'),
                             ], related='type_id.type', readonly=True,
                            store=True)
    value = fields.Float('Value')
    product_id = fields.Many2one('product.product', 'Product',
                                 required=True, ondelete='cascade')

    @api.onchange('type_id')
    def onchange_type_id(self):
        if self.type_id.type == 'fixed':
            self.value = self.type_id.default_value


class product_product(models.Model):
    _inherit = 'product.product'

    costs_structure_id = fields.Many2one('product.costs.structure',
                                        'Cost structure')
    costs_line_ids = fields.One2many('product.product.costs', 'product_id',
                                     'Costs')

    @api.one
    def _get_bom_price(self):
        """
        Get purchase price of related BoMs
        """
        total = 0
        uom_obj = self.env['product.uom']
        bom = self.bom_ids and self.bom_ids[0]
        if bom:
            # TODO: take in account the start and end dates
            for component in bom.bom_line_ids:
                product = component.product_id
                price = uom_obj.\
                    _compute_price(from_uom_id=product.uom_id.id,
                                   price=product.standard_price,
                                   to_uom_id=component.product_uom.id)
                total += price * component.product_qty
            uom_price = uom_obj.\
                _compute_price(from_uom_id=self.uom_id.id,
                               price=total,
                               to_uom_id=bom.product_uom.id)
            total = uom_price * bom.product_qty
        return total

    @api.one
    def _get_bom_routing_price(self):
        """
        Get routing price of related BoMs
        """
        total = 0
        product_obj = self.env['product.product']
        uom_obj = self.env['product.uom']
        workcenter_obj = self.env['mrp.workcenter']
        bom = self.bom_ids and self.bom_ids[0]
        factor = self.uom_id.factor / bom.product_uom.factor
        sub_boms = bom._bom_explode(bom=bom, product=self, factor=factor / bom.product_qty)
        def process_bom(bom_dict, factor=1):
            sum_strd = 0
            prod = product_obj.browse(bom_dict['product_id'])
            prod_qty = factor * bom_dict['product_qty']
            product_uom = uom_obj.browse(bom_dict['product_uom'])
            std_price = uom_obj._compute_price(from_uom_id=prod.uom_id.id,
                                               price=prod.standard_price,
                                               to_uom_id=product_uom.id)
            sum_strd = prod_qty * std_price
            return sum_strd
        def process_workcenter(wrk):
            workcenter = workcenter_obj.browse(wrk['workcenter_id'])
            cost_cycle = wrk['cycle'] * workcenter.costs_cycle
            cost_hour = wrk['hour'] * workcenter.costs_hour
            total = cost_cycle + cost_hour
            return total
        parent_bom = {
                      'product_qty': bom.product_qty,
                      'product_uom': bom.product_uom.id,
                      'product_id': bom.product_id.id,
                      }
        for sub_bom in (sub_boms and sub_boms[0]) or [parent_bom]:
            total += process_bom(sub_bom)
        for wrk in (sub_boms and sub_boms[1]):
            total += process_workcenter(wrk)
        return total

    @api.onchange('costs_structure_id')
    def onchange_cost_structure_id(self):
        self.costs_line_ids = False
        lines = []
        formula_lines = self.env['product.costs.structure.line']
        for line in self.costs_structure_id.line_ids:
            value = 0
            if line.type == 'fixed':
                value = line.default_value
            elif line.type == 'formula':
                formula_lines += line
                continue
            elif line.type == 'bom':
                value = self._get_bom_price()[0]
            elif line.type == 'bom_routing':
                value = self._get_bom_routing_price()[0]
            line_vals = {
                         'type_id': line.type_id.id,
                         'sequence': line.sequence,
                         'value': value,
                         }
            lines.append(line_vals)
        for line in formula_lines:
            value = sum(l['value'] for l in lines
                        if l['type_id'] in line.type_id.formula_ids.ids)
            line_vals = {
                         'type_id': line.type_id.id,
                         'sequence': line.sequence,
                         'value': value,
                         }
            lines.append(line_vals)
        self.costs_line_ids = lines

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
