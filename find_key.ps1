Get-ChildItem 'Y:\ApolloSupport\backend' -File | Select-Object Name, Length | Where-Object { $_.Name -match 'ed|key' }
