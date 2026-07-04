console.log('===== 调试快捷新增零件名称 =====');

// 模拟表单数据
const testData = {
  primary_category: '测试分类',
  secondary_category: '测试二级',
  customer_part_name: '测试客户件',
  remark: '测试备注'
};

console.log('发送的数据:', testData);
console.log('JSON格式:', JSON.stringify(testData, null, 2));

// 获取token
const token = localStorage.getItem('token');
console.log('Token存在:', !!token);
console.log('Token前20字符:', token ? token.substring(0, 20) + '...' : 'null');

// 测试请求
fetch('http://localhost:5175/api/v1/part-names', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify(testData)
})
.then(response => {
  console.log('响应状态:', response.status);
  console.log('响应头:', response.headers);
  return response.json();
})
.then(data => {
  console.log('响应数据:', data);
})
.catch(error => {
  console.error('请求错误:', error);
});

console.log('===== 调试完成 =====');
