from __future__ import print_function, unicode_literals

import sys
import io
import copy

from PyPDF2 import PdfFileWriter, PdfFileReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import Frame, Table, TableStyle


class MaskFactory(object):
    pagesize = A4

    def get_canvas(self, packet):
        return canvas.Canvas(packet, pagesize=self.pagesize)

    def get_mask_page(self, context):
        packet = io.BytesIO()
        c = self.get_canvas(packet)
        self.render(c, context)
        c.showPage()
        c.save()
        packet.seek(0)
        return PdfFileReader(packet).getPage(0)

    def render(self, canvas, context):
        raise NotImplementedError()


class MultipleMaskFactory(object):
    def __init__(self, factories):
        self.factories = factories

    def get_mask_page(self, context):
        page = self.factories[0].get_mask_page(context)
        for f in self.factories[1:]:
            page.mergePage(f.get_mask_page(context))
        return page


class EmptyPageMask(MaskFactory):
    def render(self, canvas, context):
        return


class TaskPageMask(MaskFactory):
    def __init__(self, box_height, left_margin, right_margin, top_margin):
        self.left_margin = left_margin
        self.right_margin = right_margin
        self.top_margin = top_margin
        self.box_height = box_height
        self.box_width = self.pagesize[0] - left_margin - right_margin
        self.bottom_margin = self.pagesize[1] - top_margin - box_height
        super(TaskPageMask, self).__init__()

    def get_canvas(self, packet):
        canvas = super(TaskPageMask, self).get_canvas(packet)
        canvas.setStrokeColor(colors.black)
        canvas.setFillColor(colors.white)
        canvas.setLineWidth(0.2 * mm)
        return canvas

    def render(self, canvas, context):
        canvas.rect(self.left_margin, self.bottom_margin,
                    self.box_width, self.box_height,
                    stroke=1, fill=1)

        data = [
            ('Last name:', context['student']['last_name']),
            ('Name:', context['student']['first_name']),
            ('Teacher:', '{} {}'.format(context['teacher']['last_name'],
                                        context['teacher']['first_name'])),
            ('ID:', context['student']['id']),
            ('School:', context['school']),
        ]

        t = Table(data, (30 * mm, self.box_width - 32 * mm),
                  [(self.box_height - 3 * mm) / len(data)] * len(data))
        s = TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (0, -1), 13),
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ])
        t.setStyle(s)
        f = Frame(self.left_margin, self.bottom_margin,
                  self.box_width, self.box_height,
                  leftPadding=1 * mm, rightPadding=1 * mm,
                  topPadding=2.5 * mm, bottomPadding=0 * mm)
        f.addFromList([t], canvas)


class AnswerSheetMask(MaskFactory):
    def __init__(self, box_height, box_width, right_margin, top_margin):
        self.right_margin = right_margin
        self.top_margin = top_margin
        self.box_height = box_height
        self.box_width = box_width
        self.left_margin = self.pagesize[0] - right_margin - box_width
        self.bottom_margin = self.pagesize[1] - top_margin - box_height
        super(AnswerSheetMask, self).__init__()

    def get_canvas(self, packet):
        canvas = super(AnswerSheetMask, self).get_canvas(packet)
        canvas.setStrokeColor(colors.black)
        canvas.setFillColor(colors.white)
        canvas.setLineWidth(0.2 * mm)
        canvas.setFont('Helvetica', 8)
        return canvas

    def render(self, canvas, context):
        canvas.rect(self.left_margin, self.bottom_margin,
                    self.box_width, self.box_height,
                    stroke=0, fill=1)
        canvas.setFillColor(colors.black)
        canvas.drawString(
            self.left_margin + 2 * mm, self.bottom_margin + 2 * mm,
            'ID: {}'.format(context['student']['id']))
        canvas.drawRightString(
            self.left_margin + self.box_width - 2 * mm,
            self.bottom_margin + 2 * mm,
            '(Seite {})'.format(context['page_num']))


def merge(context, students, mapping, input_pdf):
    output_pdf = PdfFileWriter()

    for student in students:
        context.update({
            'student': student,
        })

        for page_num in range(input_pdf.getNumPages()):
            context.update({
                'page_num': page_num,
            })
            page = copy.copy(input_pdf.getPage(page_num))
            mask = mapping[page_num].get_mask_page(context)
            page.mergePage(mask)
            output_pdf.addPage(page)

    return output_pdf


#####################################
# Document generation configuration #
#####################################

simple_header_mask = AnswerSheetMask(box_height=10 * mm, box_width=42 * mm,
                                     right_margin=11 * mm, top_margin=15 * mm)

# Each entry in the following list corresponds to a page in the input PDF
mapping = [
    EmptyPageMask(),
    MultipleMaskFactory([
        TaskPageMask(top_margin=28 * mm, box_height=25 * mm,
                     left_margin=20.5 * mm, right_margin=14.5 * mm),
        simple_header_mask,
    ]),
    simple_header_mask,
    simple_header_mask,
    simple_header_mask,
]

# This would be subsistuted with the actual students queryset
students = [
    {'first_name': 'Jonathan',
     'last_name': 'Stoppani',
     'id': 123455},
    {'first_name': 'Vanessa',
     'last_name': 'Tay',
     'id': 98635},
    {'first_name': 'Jakub',
     'last_name': 'Janoszek',
     'id': 19757},
]

# Some dummy data to get started with
context = {
    'teacher': {
        'first_name': 'Urs',
        'last_name': 'Moser',
    },
    'school': 'DIVIO Test School',
}


#######################################
# Document generation for whole class #
#######################################

input_path, output_path = sys.argv[1], sys.argv[2]

with open(input_path, 'rb') as fh:
    input_pdf = PdfFileReader(fh)
    output_pdf = merge(context, students, mapping, input_pdf)

    with open(output_path, 'wb') as fh:
        output_pdf.write(fh)
