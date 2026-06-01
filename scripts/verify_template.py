import re
content = open('templates/sales/quote_edit.html', encoding='utf-8').read()
print('<script>: ' + str(content.count('<script')) + ', </script>: ' + str(content.count('</script>')))
print('<div>: ' + str(content.count('<div')) + ', </div>: ' + str(content.count('</div>')))
checks = ['treatment-list-container', 'modalTreat', 'inpMoldCost', 'selMoldDiscount',
          'moldDiscountMode', 'loadTreatments', 'addTreatmentRow', 'getTreatFeeForCalc',
          'dispSurfaceFee', 'dispMoldCost', 'updateMoldEffectiveCost',
          'onTreatSelectChange', 'treatItemList', 'btnAddTreat']
for c in checks:
    status = 'FOUND' if c in content else 'MISSING'
    print('  ' + c + ': ' + status)
