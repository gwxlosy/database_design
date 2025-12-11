#检查用户对账本操作权限
    public List<Record> getRecords(Long ledgerId, String startDate, String endDate, String username) {
        User user = userMapper.selectByUsername(username);
        
        // 检查权限
        LedgerMember member = ledgerMemberMapper.selectByLedgerAndUser(ledgerId, user.getId());
        if (member == null) {
            throw new RuntimeException("没有访问权限");
        }
        
        LocalDate start = startDate != null ? LocalDate.parse(startDate) : null;
        LocalDate end = endDate != null ? LocalDate.parse(endDate) : null;
        
        return recordMapper.selectByLedgerIdWithDetails(ledgerId, start, end);
    }